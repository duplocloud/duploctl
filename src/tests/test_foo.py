import pytest

@pytest.fixture
def fixt(request):
    return request.param * 3

@pytest.mark.parametrize("test_data", ["cronjob"], indirect=True)
class TestFooResources:
  def test_indirect(self, test_data, duplo):
    print(test_data)
    print(duplo.tenant)
