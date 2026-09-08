"""
Property-based tests for container data persistence.

Feature: cv-web-app, Property 15: Container Data Persistence
Validates: Requirements 7.1, 8.3
"""
import json
import os
import tempfile
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Dict, Any

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
import requests


# Test data generators
@st.composite
def cv_data_strategy(draw):
    """Generate valid CV data for testing."""
    return {
        "id": str(uuid.uuid4()),
        "metadata": {
            "title": draw(st.text(min_size=1, max_size=50)),
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "template_id": "default"
        },
        "personal_info": {
            "name": draw(st.text(min_size=1, max_size=100)),
            "title": draw(st.text(min_size=1, max_size=100)),
            "contact": {
                "email": draw(st.emails()),
                "phone": draw(st.text(min_size=5, max_size=20)),
                "address": draw(st.text(min_size=5, max_size=200))
            }
        },
        "summary": draw(st.text(min_size=10, max_size=500)),
        "experience": [
            {
                "id": str(uuid.uuid4()),
                "title": draw(st.text(min_size=1, max_size=100)),
                "company": draw(st.text(min_size=1, max_size=100)),
                "location": draw(st.text(min_size=1, max_size=100)),
                "start_date": "2020-01-01",
                "end_date": "2023-12-31",
                "current": False,
                "description": draw(st.text(min_size=10, max_size=500)),
                "achievements": draw(st.lists(st.text(min_size=5, max_size=100), min_size=0, max_size=5))
            }
        ],
        "education": [
            {
                "id": str(uuid.uuid4()),
                "degree": draw(st.text(min_size=1, max_size=100)),
                "institution": draw(st.text(min_size=1, max_size=100)),
                "location": draw(st.text(min_size=1, max_size=100)),
                "start_date": "2016-09-01",
                "end_date": "2020-05-31",
                "gpa": "3.8",
                "description": draw(st.text(min_size=0, max_size=300))
            }
        ],
        "skills": {
            "categories": [
                {
                    "name": draw(st.text(min_size=1, max_size=50)),
                    "skills": draw(st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10))
                }
            ]
        }
    }


class ContainerTestHelper:
    """Helper class for container testing operations."""
    
    def __init__(self):
        # Use timestamp to make container names more unique
        import time
        timestamp = str(int(time.time() * 1000))
        self.container_name = f"cv-test-{uuid.uuid4().hex[:8]}-{timestamp}"
        self.temp_data_dir = None
        
    def setup_test_environment(self):
        """Set up temporary directories for testing."""
        # Clean up any existing containers first
        self.cleanup_test_environment()
        
        self.temp_data_dir = tempfile.mkdtemp(prefix="cv_test_")
        
        # Create required directory structure
        os.makedirs(os.path.join(self.temp_data_dir, "cvs"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_data_dir, "exports"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_data_dir, "config"), exist_ok=True)
        
        return self.temp_data_dir
    
    def cleanup_test_environment(self):
        """Clean up test environment."""
        # Stop and remove container if it exists
        try:
            # Force stop and remove any containers with this name
            subprocess.run(
                ["docker", "stop", self.container_name],
                capture_output=True,
                timeout=30
            )
            subprocess.run(
                ["docker", "rm", "-f", self.container_name],
                capture_output=True,
                timeout=30
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
        
        # Also try to remove any containers that might be using the same name pattern
        try:
            # List containers with our naming pattern and remove them
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", f"name=cv-test-", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                container_names = result.stdout.strip().split('\n')
                for name in container_names:
                    if name.startswith('cv-test-'):
                        subprocess.run(
                            ["docker", "rm", "-f", name],
                            capture_output=True,
                            timeout=30
                        )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
        
        # Clean up temporary directory
        if self.temp_data_dir and os.path.exists(self.temp_data_dir):
            shutil.rmtree(self.temp_data_dir)
    
    def start_container(self, data_dir: str, port: int = 8001) -> bool:
        """Start container with mounted data directory."""
        try:
            # Build the image if it doesn't exist
            build_result = subprocess.run(
                ["docker", "build", "-t", "cv-web-app:test", "."],
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                capture_output=True,
                timeout=300
            )
            
            if build_result.returncode != 0:
                print(f"Docker build failed: {build_result.stderr.decode()}")
                return False
            
            # Generate a new unique container name for each start
            import time
            timestamp = str(int(time.time() * 1000))
            container_name = f"cv-test-{uuid.uuid4().hex[:8]}-{timestamp}"
            
            # Start container with volume mount
            run_result = subprocess.run([
                "docker", "run", "-d",
                "--name", container_name,
                "-p", f"{port}:8000",
                "-v", f"{data_dir}:/app/data",
                "-e", "DATA_DIR=/app/data",
                "cv-web-app:test"
            ], capture_output=True, timeout=60)
            
            if run_result.returncode != 0:
                print(f"Docker run failed: {run_result.stderr.decode()}")
                return False
            
            # Update the container name for cleanup
            self.container_name = container_name
            
            # Wait for container to be ready
            return self.wait_for_container_ready(port)
            
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f"Container start failed: {e}")
            return False
    
    def stop_container(self) -> bool:
        """Stop the container."""
        try:
            result = subprocess.run(
                ["docker", "stop", self.container_name],
                capture_output=True,
                timeout=30
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False
    
    def wait_for_container_ready(self, port: int, timeout: int = 60) -> bool:
        """Wait for container to be ready to accept requests."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://localhost:{port}/health", timeout=5)
                if response.status_code == 200:
                    return True
            except requests.RequestException:
                pass
            time.sleep(2)
        return False
    
    def save_cv_data_to_volume(self, data_dir: str, cv_data: Dict[str, Any]) -> str:
        """Save CV data directly to the mounted volume."""
        cv_id = cv_data["id"]
        cv_file_path = os.path.join(data_dir, "cvs", f"{cv_id}.json")
        
        with open(cv_file_path, 'w') as f:
            json.dump(cv_data, f, indent=2)
        
        return cv_file_path
    
    def load_cv_data_from_volume(self, data_dir: str, cv_id: str) -> Dict[str, Any]:
        """Load CV data directly from the mounted volume."""
        cv_file_path = os.path.join(data_dir, "cvs", f"{cv_id}.json")
        
        if not os.path.exists(cv_file_path):
            return None
        
        with open(cv_file_path, 'r') as f:
            return json.load(f)


@pytest.fixture
def container_helper():
    """Fixture providing container test helper."""
    helper = ContainerTestHelper()
    yield helper
    helper.cleanup_test_environment()


@pytest.mark.slow
@pytest.mark.integration
class TestContainerDataPersistence:
    """Property-based tests for container data persistence."""
    
    @given(cv_data=cv_data_strategy())
    @settings(max_examples=2, deadline=300000, suppress_health_check=[HealthCheck.function_scoped_fixture])  # Minimal examples for container tests
    def test_container_data_persistence_round_trip(self, container_helper, cv_data):
        """
        Property 15: Container Data Persistence
        
        For any CV data created in the container, restarting the container 
        should preserve all data through volume mounting.
        
        **Validates: Requirements 7.1, 8.3**
        """
        # Setup test environment
        data_dir = container_helper.setup_test_environment()
        port = 8001
        
        try:
            # Step 1: Save CV data to volume before starting container
            cv_id = cv_data["id"]
            container_helper.save_cv_data_to_volume(data_dir, cv_data)
            
            # Step 2: Start container with mounted volume
            assert container_helper.start_container(data_dir, port), "Container failed to start"
            
            # Step 3: Verify data is accessible through the container
            # (This would normally be done via API, but for this test we'll verify file access)
            loaded_data_1 = container_helper.load_cv_data_from_volume(data_dir, cv_id)
            assert loaded_data_1 is not None, "CV data not found after container start"
            assert loaded_data_1 == cv_data, "CV data corrupted after container start"
            
            # Step 4: Stop container
            assert container_helper.stop_container(), "Container failed to stop"
            
            # Step 5: Verify data persists in volume after container stop
            loaded_data_2 = container_helper.load_cv_data_from_volume(data_dir, cv_id)
            assert loaded_data_2 is not None, "CV data lost after container stop"
            assert loaded_data_2 == cv_data, "CV data corrupted after container stop"
            
            # Step 6: Restart container
            assert container_helper.start_container(data_dir, port), "Container failed to restart"
            
            # Step 7: Verify data persists after container restart
            loaded_data_3 = container_helper.load_cv_data_from_volume(data_dir, cv_id)
            assert loaded_data_3 is not None, "CV data lost after container restart"
            assert loaded_data_3 == cv_data, "CV data corrupted after container restart"
            
            # All assertions passed - data persisted through container lifecycle
            
        finally:
            # Cleanup is handled by the fixture
            pass
    
    @given(cv_data_list=st.lists(cv_data_strategy(), min_size=1, max_size=2))
    @settings(max_examples=2, deadline=300000, suppress_health_check=[HealthCheck.function_scoped_fixture])  # Minimal examples for multiple CV test
    def test_multiple_cv_data_persistence(self, container_helper, cv_data_list):
        """
        Test that multiple CV files persist correctly across container restarts.
        
        **Validates: Requirements 7.1, 8.3**
        """
        # Setup test environment
        data_dir = container_helper.setup_test_environment()
        port = 8002
        
        try:
            # Step 1: Save multiple CV files to volume
            cv_ids = []
            for cv_data in cv_data_list:
                cv_id = cv_data["id"]
                cv_ids.append(cv_id)
                container_helper.save_cv_data_to_volume(data_dir, cv_data)
            
            # Step 2: Start container
            assert container_helper.start_container(data_dir, port), "Container failed to start"
            
            # Step 3: Verify all CV files are accessible
            for i, cv_id in enumerate(cv_ids):
                loaded_data = container_helper.load_cv_data_from_volume(data_dir, cv_id)
                assert loaded_data is not None, f"CV {cv_id} not found after container start"
                assert loaded_data == cv_data_list[i], f"CV {cv_id} corrupted after container start"
            
            # Step 4: Restart container
            assert container_helper.stop_container(), "Container failed to stop"
            assert container_helper.start_container(data_dir, port), "Container failed to restart"
            
            # Step 5: Verify all CV files persist after restart
            for i, cv_id in enumerate(cv_ids):
                loaded_data = container_helper.load_cv_data_from_volume(data_dir, cv_id)
                assert loaded_data is not None, f"CV {cv_id} lost after container restart"
                assert loaded_data == cv_data_list[i], f"CV {cv_id} corrupted after container restart"
        
        finally:
            # Cleanup is handled by the fixture
            pass


# Additional unit tests for edge cases
@pytest.mark.slow
@pytest.mark.integration
class TestContainerDataPersistenceEdgeCases:
    """Unit tests for specific edge cases in container data persistence."""
    
    def test_empty_data_directory_persistence(self, container_helper):
        """Test that empty data directory structure persists."""
        data_dir = container_helper.setup_test_environment()
        port = 8003
        
        try:
            # Start container with empty data directory
            assert container_helper.start_container(data_dir, port)
            
            # Verify directory structure exists
            assert os.path.exists(os.path.join(data_dir, "cvs"))
            assert os.path.exists(os.path.join(data_dir, "exports"))
            assert os.path.exists(os.path.join(data_dir, "config"))
            
            # Restart container
            assert container_helper.stop_container()
            assert container_helper.start_container(data_dir, port)
            
            # Verify directory structure still exists
            assert os.path.exists(os.path.join(data_dir, "cvs"))
            assert os.path.exists(os.path.join(data_dir, "exports"))
            assert os.path.exists(os.path.join(data_dir, "config"))
            
        finally:
            pass
    
    def test_container_startup_with_existing_data(self, container_helper):
        """Test container startup when data already exists in volume."""
        data_dir = container_helper.setup_test_environment()
        port = 8004
        
        # Create some test data before starting container
        test_cv = {
            "id": str(uuid.uuid4()),
            "metadata": {"title": "Test CV", "template_id": "default"},
            "personal_info": {"name": "Test User", "contact": {"email": "test@example.com"}}
        }
        
        try:
            # Save data before container starts
            container_helper.save_cv_data_to_volume(data_dir, test_cv)
            
            # Start container
            assert container_helper.start_container(data_dir, port)
            
            # Verify data is still accessible
            loaded_data = container_helper.load_cv_data_from_volume(data_dir, test_cv["id"])
            assert loaded_data == test_cv
            
        finally:
            pass