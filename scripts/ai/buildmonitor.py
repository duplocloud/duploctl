#!/usr/bin/env python3
import os
import subprocess
import time
import boto3
from botocore.exceptions import ClientError
from pathlib import Path

def get_s3_paths():
    """Get S3 paths from environment variables."""
    bucket = os.getenv('BUILD_STORAGE_PATH')
    base_path = os.getenv('BUILD_FOLDER_PATH')
    spec_path = os.getenv('BUILD_SPEC_PATH')

    if not all([bucket, base_path, spec_path]):
        raise ValueError("Required environment variables are not set: BUILD_STORAGE_PATH, BUILD_FOLDER_PATH, BUILD_SPEC_PATH")

    # Extract base filename from spec path (e.g., sre004-2025-02-07-17-15-45.json -> sre004-2025-02-07-17-15-45)
    base_filename = Path(spec_path).name.replace('.json', '')

    return {
        'bucket': bucket,
        'base_path': base_path,
        'log_key': f"{base_path}/{base_filename}.log",
        'complete_key': f"{base_path}/{base_filename}.complete"
    }

def s3_upload(key, src_file):
    """Upload a file to S3."""
    if not os.path.isfile(src_file):
        print(f'**** Requested file {src_file} does not exist yet')
        return
    
    try:
        s3_info = get_s3_paths()
        s3_client = boto3.client('s3')
        s3_client.upload_file(src_file, s3_info['bucket'], key)
        print(f'Successfully uploaded {src_file} to {s3_info["bucket"]}/{key}')
    except ClientError as e:
        print(f'Error uploading to S3: {str(e)}')
    except Exception as e:
        print(f'Error: {str(e)}')

def upload_logs(is_running):
    """Upload build logs and completion marker to S3."""
    try:
        s3_info = get_s3_paths()

        # Always try to upload the current state of the build log if it exists
        if os.path.exists('/tmp/build.log'):
            # Upload current logs
            s3_upload(s3_info['log_key'], '/tmp/build.log')
            print(f"Uploaded build logs to {s3_info['log_key']}")
        else:
            print("Build log file not found at /tmp/build.log")
        
        # If build is complete, upload marker and final logs
        if not is_running:
            # Upload final version of build logs
            if os.path.exists('/tmp/build.log'):
                s3_upload(s3_info['log_key'], '/tmp/build.log')
                print(f"Uploaded final build logs to {s3_info['log_key']}")

            # Create and upload completion marker based on build status
            complete_marker = '/tmp/build.complete'

            # Check build status file
            status = "Failure"  # Default to failure
            if os.path.exists('/tmp/build.status'):
                with open('/tmp/build.status', 'r') as f:
                    status = f.read().strip()

            # Write status to completion marker
            with open(complete_marker, 'w') as f:
                f.write(status)

            s3_upload(s3_info['complete_key'], complete_marker)
            print(f"Uploaded completion marker with status: {status}")
            
    except Exception as e:
        print(f"Error in upload_logs: {str(e)}")
        import traceback
        print(f"Full exception: {traceback.format_exc()}")

def is_build_running():
    """Check if the Docker build is still running."""
    try:
        # Method 1: Check for the build.sh process
        ps_result = subprocess.run(
            ['pgrep', '-f', 'build.sh'],
            capture_output=True,
            text=True
        )

        if ps_result.stdout.strip():
            print("Builder process is running")
            return True

        # Method 2: Check supervisord log for completion status
        try:
            with open('/var/log/supervisord.log', 'r') as f:
                log_lines = f.readlines()
                # Look for the most recent builder status
                for line in reversed(log_lines):
                    if 'exited: builder' in line:
                        print(f"Found builder exit log: {line.strip()}")
                        # If we find an exit log, the process is not running
                        return False
        except Exception as e:
            print(f"Error reading supervisor log: {str(e)}")

        # Method 3: Check if there are any active docker build processes
        docker_ps = subprocess.run(
            ['docker', 'ps', '--filter', 'status=running', '--format', '{{.Command}}'],
            capture_output=True,
            text=True
        )
        if 'build' in docker_ps.stdout.lower():
            print("Docker build process is running")
            return True

        print("No active build process found")
        return False

    except Exception as e:
        print(f"Error checking build status: {str(e)}")
        # Log the full exception for debugging
        import traceback
        print(f"Full exception: {traceback.format_exc()}")
        return False

def main():
    print("Starting Build Monitor")
    
    # Initial delay to let the build process start
    time.sleep(5)
    
    while True:
        try:
            running = is_build_running()
            upload_logs(running)
            
            if not running:
                print("Build process has completed")
                # Upload logs one final time
                upload_logs(False)
                break
                
            time.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            time.sleep(30)  # Continue monitoring even if there's an error
    
    print("Build monitoring completed")

if __name__ == '__main__':
    main()
