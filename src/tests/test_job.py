import pytest
import time
from duplocloud.errors import DuploError, DuploFailedResource, DuploStillWaiting
from .conftest import get_test_data

@pytest.fixture(scope="class")
def job_resource(duplo):
    """Fixture to load the Job resource and define Job name."""
    resource = duplo.load("job")
    resource.duplo.wait = True
    job_name = f"duploctl"
    return resource, job_name

def execute_test(func, *args, **kwargs):
    """Helper function to execute a test and handle errors."""
    try:
        return func(*args, **kwargs)
    except (DuploError, DuploFailedResource, DuploStillWaiting) as e:
        pytest.fail(f"Test failed: {e}")

@pytest.mark.integration
@pytest.mark.k8s
@pytest.mark.job
class TestJob:

    @pytest.mark.dependency(name="create_job", depends=["asg_restored"], scope="session")
    @pytest.mark.order(75)
    def test_create_job(self, job_resource):
        """Test creating a new job."""
        r, job_name = job_resource
        body = get_test_data("job")
        # If the job already completed successfully from a prior run, reuse it.
        try:
            existing = r.find(job_name)
            if existing:
                conds = existing.get("status", {}).get("conditions", [])
                completed = any(c["type"] == "Complete" and c["status"] == "True" for c in conds)
                if completed:
                    print(f"Job '{job_name}' already completed successfully — reusing")
                    return
                print(f"Job '{job_name}' exists but not completed — deleting before recreate")
                r.delete(job_name)
        except DuploError:
            pass
        response = execute_test(r.create, body=body)
        assert "ran successfully" in response["message"]
        time.sleep(30)  # Allow time for pods to be created

    @pytest.mark.dependency(depends=["create_job"], scope="session")
    @pytest.mark.order(76)
    def test_find_job(self, job_resource):
        """Test finding a specific job and verify parallelism spec."""
        r, job_name = job_resource
        job = execute_test(r.find, job_name)
        assert job["metadata"]["name"] == job_name
        assert job["spec"]["parallelism"] == 2
        assert job["spec"]["completions"] == 4

    @pytest.mark.dependency(depends=["create_job"], scope="session")
    @pytest.mark.order(76)
    def test_list_jobs(self, job_resource):
        """Test listing all jobs."""
        r, _ = job_resource
        jobs = execute_test(r.list)
        assert isinstance(jobs, list) and len(jobs) > 0

    @pytest.mark.dependency(depends=["create_job"], scope="session")
    @pytest.mark.order(76)
    def test_get_pods(self, job_resource):
        """Test getting pods for a job."""
        r, job_name = job_resource
        pods = execute_test(r.pods, job_name)
        assert isinstance(pods, list)
        if len(pods) > 0:
            assert pods[0]["ControlledBy"]["QualifiedType"] == "kubernetes:batch/v1/Job"
            assert pods[0]["Name"] == job_name

    @pytest.mark.dependency(depends=["create_job"], scope="session")
    @pytest.mark.order(993)
    def test_delete_job(self, job_resource):
        """Test deleting a job."""
        r, job_name = job_resource
        response = execute_test(r.delete, job_name)
        assert "deleted" in response["message"].lower()
