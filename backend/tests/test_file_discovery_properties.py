"""
Property-based tests for file discovery and system compatibility.

Feature: cv-web-app, Property 16: File System Compatibility
Validates: Requirements 7.4, 7.5
"""
import json
import os
import tempfile
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from app.models.cv_models import CVModel, PersonalInfo, CVMetadata, ContactInfo
from app.services.cv_service import CVService
from app.services.file_service import FileService
from tests import v2_helpers as v2


# Test data generators for external CV files
@st.composite
def external_cv_file_strategy(draw):
    """Generate valid CV data that could be created outside the application."""
    cv_id = str(uuid.uuid4())
    
    # Generate CV data that matches the expected JSON structure
    cv_data = {
        "id": cv_id,
        "metadata": {
            "title": draw(st.text(min_size=1, max_size=100)),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "template_id": draw(st.sampled_from(["default", "modern", "classic"]))
        },
        "personal_info": {
            "name": draw(st.text(min_size=1, max_size=100)),
            "title": draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
            "contact": {
                "address": draw(st.one_of(st.none(), st.text(min_size=5, max_size=200))),
                "phone": draw(st.one_of(st.none(), st.text(min_size=5, max_size=20))),
                "email": draw(st.one_of(st.none(), st.emails())),
                "linkedin": draw(st.one_of(st.none(), st.text(min_size=5, max_size=100))),
                "website": draw(st.one_of(st.none(), st.text(min_size=5, max_size=100)))
            }
        },
        "summary": draw(st.one_of(st.none(), st.text(min_size=10, max_size=500))),
        "experience": draw(st.lists(
            st.fixed_dictionaries({
                "id": st.just(str(uuid.uuid4())),
                "title": st.text(min_size=1, max_size=100),
                "company": st.text(min_size=1, max_size=100),
                "location": st.one_of(st.none(), st.text(min_size=1, max_size=100)),
                "start_date": st.text(min_size=1, max_size=20),
                "end_date": st.one_of(st.none(), st.text(min_size=1, max_size=20)),
                "current": st.booleans(),
                "description": st.one_of(st.none(), st.text(min_size=10, max_size=500)),
                "achievements": st.lists(st.text(min_size=5, max_size=100), min_size=0, max_size=5)
            }),
            min_size=0, max_size=3
        )),
        "education": draw(st.lists(
            st.fixed_dictionaries({
                "id": st.just(str(uuid.uuid4())),
                "degree": st.text(min_size=1, max_size=100),
                "institution": st.text(min_size=1, max_size=100),
                "location": st.one_of(st.none(), st.text(min_size=1, max_size=100)),
                "start_date": st.one_of(st.none(), st.text(min_size=1, max_size=20)),
                "end_date": st.one_of(st.none(), st.text(min_size=1, max_size=20)),
                "gpa": st.one_of(st.none(), st.text(min_size=1, max_size=10)),
                "description": st.one_of(st.none(), st.text(min_size=10, max_size=300))
            }),
            min_size=0, max_size=3
        )),
        "skills": {
            "categories": draw(st.lists(
                st.fixed_dictionaries({
                    "name": st.text(min_size=1, max_size=50),
                    "skills": st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10)
                }),
                min_size=0, max_size=5
            ))
        },
        "certifications": draw(st.lists(
            st.fixed_dictionaries({
                "id": st.just(str(uuid.uuid4())),
                "name": st.text(min_size=1, max_size=100),
                "issuer": st.text(min_size=1, max_size=100),
                "date": st.one_of(st.none(), st.text(min_size=1, max_size=20)),
                "expiry_date": st.one_of(st.none(), st.text(min_size=1, max_size=20))
            }),
            min_size=0, max_size=3
        ))
    }
    
    return cv_data


@st.composite
def multiple_external_cv_files_strategy(draw):
    """Generate multiple external CV files for testing bulk discovery."""
    num_files = draw(st.integers(min_value=1, max_value=5))
    cv_files = []
    
    for _ in range(num_files):
        cv_data = draw(external_cv_file_strategy())
        cv_files.append(cv_data)
    
    return cv_files


@pytest.fixture(scope="function")
def temp_data_dir():
    """Fixture providing temporary data directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="cv_discovery_test_")
    yield temp_dir
    # Ensure cleanup even if test fails
    try:
        shutil.rmtree(temp_dir)
    except OSError:
        pass  # Ignore cleanup errors


@pytest.fixture
def file_service(temp_data_dir):
    """Fixture providing FileService with temporary directory."""
    return FileService(data_directory=temp_data_dir)


@pytest.fixture
def cv_service(file_service):
    """Fixture providing CVService with temporary FileService."""
    return CVService(file_service=file_service)


def create_external_cv_file(data_dir: str, cv_data: Dict[str, Any]) -> str:
    """
    Create a CV file externally (simulating manual file creation).
    
    Args:
        data_dir: Data directory path
        cv_data: CV data dictionary
        
    Returns:
        Path to the created file
    """
    cvs_dir = Path(data_dir) / "cvs"
    cvs_dir.mkdir(parents=True, exist_ok=True)
    
    cv_id = cv_data["id"]
    file_path = cvs_dir / f"{cv_id}.json"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(cv_data, f, indent=2, ensure_ascii=False)
    
    return str(file_path)


class TestFileSystemCompatibility:
    """Property-based tests for file system compatibility and discovery."""
    
    @given(external_cv=external_cv_file_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_external_cv_file_discovery(self, cv_service, temp_data_dir, external_cv):
        """
        Property 16: File System Compatibility
        
        For any CV files created outside the application, the system should 
        automatically detect and load them on startup.
        
        **Validates: Requirements 7.4, 7.5**
        """
        # Step 1: Create CV file externally (simulating manual file creation)
        cv_id = external_cv["id"]
        file_path = create_external_cv_file(temp_data_dir, external_cv)
        
        # Verify file was created externally
        assert os.path.exists(file_path), "External CV file should be created"
        
        # Step 2: Use CV service to discover files (simulating application startup)
        discovered_cvs = cv_service.discover_cvs()
        
        # Step 3: Verify that externally created CV is discovered
        discovered_ids = [cv.id for cv in discovered_cvs.cvs]
        assert cv_id in discovered_ids, f"Externally created CV {cv_id} should be discovered by the system"
        
        # Step 4: Verify that discovered CV data matches original external data
        discovered_cv = next(cv for cv in discovered_cvs.cvs if cv.id == cv_id)
        
        # Compare core fields to ensure data integrity
        assert discovered_cv.id == external_cv["id"], "CV ID should be preserved"
        assert v2.cv_title(discovered_cv) == external_cv["metadata"]["title"], "CV title should be preserved"
        assert v2.full_name(discovered_cv) == external_cv["personal_info"]["name"], "Personal name should be preserved"
        
        # Verify contact information
        if external_cv["personal_info"]["contact"]["email"]:
            assert v2.section_content(discovered_cv, "personal_info").email == external_cv["personal_info"]["contact"]["email"], "Email should be preserved"
        if external_cv["personal_info"]["contact"]["phone"]:
            assert v2.section_content(discovered_cv, "personal_info").phone == external_cv["personal_info"]["contact"]["phone"], "Phone should be preserved"
        
        # Verify collections have correct lengths
        assert len(v2.experience(discovered_cv)) == len(external_cv["experience"]), "Experience count should be preserved"
        assert len(v2.education(discovered_cv)) == len(external_cv["education"]), "Education count should be preserved"
        # The V1 to V2 migration drops blank skill entries, so compare the
        # skills that survive that filter rather than the raw count.
        expected_skills = [
            skill
            for category in external_cv["skills"]["categories"]
            for skill in category["skills"]
            if skill and skill.strip()
        ]
        assert v2.skills(discovered_cv) == expected_skills, "Skills should be preserved"
        assert len(v2.entries(discovered_cv, "certifications")) == len(
            external_cv["certifications"]
        ), "Certifications count should be preserved"
        
        # Step 5: Verify CV can be retrieved individually after discovery
        retrieved_cv_response = cv_service.get_cv(cv_id)
        retrieved_cv = retrieved_cv_response.cv
        
        assert retrieved_cv.id == cv_id, "Retrieved CV should have correct ID"
        assert v2.cv_title(retrieved_cv) == external_cv["metadata"]["title"], "Retrieved CV should have correct title"
    
    @given(external_cvs=multiple_external_cv_files_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_multiple_external_cv_files_discovery(self, cv_service, temp_data_dir, external_cvs):
        """
        Test that multiple externally created CV files are all discovered.
        
        **Validates: Requirements 7.4, 7.5**
        """
        # Step 1: Get initial CV count (should be 0 for fresh temp dir)
        initial_cvs = cv_service.discover_cvs()
        initial_count = len(initial_cvs.cvs)
        initial_ids = {cv.id for cv in initial_cvs.cvs}
        
        # Step 2: Create multiple CV files externally
        created_ids = []
        for cv_data in external_cvs:
            cv_id = cv_data["id"]
            create_external_cv_file(temp_data_dir, cv_data)
            created_ids.append(cv_id)
        
        # Step 3: Discover all CVs
        discovered_cvs = cv_service.discover_cvs()
        discovered_ids = [cv.id for cv in discovered_cvs.cvs]
        
        # Step 4: Verify all externally created CVs are discovered
        for cv_id in created_ids:
            assert cv_id in discovered_ids, f"External CV {cv_id} should be discovered"
        
        # Step 5: Verify count increased by the number of CVs we created
        expected_total = initial_count + len(external_cvs)
        assert len(discovered_cvs.cvs) == expected_total, f"Expected {expected_total} CVs (initial {initial_count} + new {len(external_cvs)}), but found {len(discovered_cvs.cvs)}"
        assert discovered_cvs.total == expected_total, f"Total count should be {expected_total}"
        
        # Step 6: Verify only our new CVs were added (no duplicates or unexpected CVs)
        new_cv_ids = set(discovered_ids) - initial_ids
        expected_new_ids = set(created_ids)
        assert new_cv_ids == expected_new_ids, f"New CVs should match created CVs. Expected: {expected_new_ids}, Got: {new_cv_ids}"
    
    @given(external_cv=external_cv_file_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_external_cv_file_listing_compatibility(self, cv_service, temp_data_dir, external_cv):
        """
        Test that externally created CVs appear in regular CV listing.
        
        **Validates: Requirements 7.4, 7.5**
        """
        # Step 1: Create CV file externally
        cv_id = external_cv["id"]
        create_external_cv_file(temp_data_dir, external_cv)
        
        # Step 2: List CVs using regular listing method
        cv_list_response = cv_service.list_cvs()
        
        # Step 3: Verify external CV appears in listing
        listed_ids = [cv.id for cv in cv_list_response.cvs]
        assert cv_id in listed_ids, "External CV should appear in regular CV listing"
        
        # Step 4: Verify CV existence check works
        assert cv_service.cv_exists(cv_id), "CV existence check should work for external CVs"
    
    @given(external_cv=external_cv_file_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_external_cv_file_service_compatibility(self, file_service, temp_data_dir, external_cv):
        """
        Test that FileService can work with externally created CV files.
        
        **Validates: Requirements 7.4, 7.5**
        """
        # Step 1: Create CV file externally
        cv_id = external_cv["id"]
        create_external_cv_file(temp_data_dir, external_cv)
        
        # Step 2: Use FileService to list files
        cv_file_ids = file_service.list_cv_files()
        
        # Step 3: Verify external CV is listed
        assert cv_id in cv_file_ids, "External CV should be listed by FileService"
        
        # Step 4: Use FileService to load external CV
        loaded_cv = file_service.load_cv(cv_id)
        
        # Step 5: Verify loaded data matches external data
        assert loaded_cv.id == external_cv["id"], "Loaded CV ID should match external CV"
        assert v2.cv_title(loaded_cv) == external_cv["metadata"]["title"], "Loaded CV title should match external CV"
        assert v2.full_name(loaded_cv) == external_cv["personal_info"]["name"], "Loaded CV name should match external CV"
        
        # Step 6: Verify CV existence check works at FileService level
        assert file_service.cv_exists(cv_id), "FileService should detect external CV existence"
    
    @given(external_cv=external_cv_file_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_mixed_internal_external_cv_discovery(self, cv_service, temp_data_dir, external_cv):
        """
        Test discovery when both internal and external CVs exist.
        
        **Validates: Requirements 7.4, 7.5**
        """
        # Step 1: Create CV through the application (internal)
        from app.models.cv_models import CVCreateRequest, CVMetadata, PersonalInfo
        
        internal_cv_request = CVCreateRequest(
            metadata=CVMetadata(title="Internal CV"),
            personal_info=PersonalInfo(name="Internal User")
        )
        internal_cv_response = cv_service.create_cv(internal_cv_request)
        internal_cv_id = internal_cv_response.cv.id
        
        # Step 2: Create CV externally
        external_cv_id = external_cv["id"]
        create_external_cv_file(temp_data_dir, external_cv)
        
        # Step 3: Discover all CVs
        discovered_cvs = cv_service.discover_cvs()
        discovered_ids = [cv.id for cv in discovered_cvs.cvs]
        
        # Step 4: Verify both internal and external CVs are discovered
        assert internal_cv_id in discovered_ids, "Internal CV should be discovered"
        assert external_cv_id in discovered_ids, "External CV should be discovered"
        assert len(discovered_cvs.cvs) >= 2, "At least both CVs should be discovered"
        
        # Step 5: Verify both can be retrieved individually
        internal_retrieved = cv_service.get_cv(internal_cv_id)
        external_retrieved = cv_service.get_cv(external_cv_id)
        
        assert v2.cv_title(internal_retrieved.cv) == "Internal CV", "Internal CV should be retrievable"
        assert v2.cv_title(external_retrieved.cv) == external_cv["metadata"]["title"], "External CV should be retrievable"
    
    def test_empty_directory_discovery(self, cv_service):
        """
        Test discovery behavior with empty CV directory.
        
        **Validates: Requirements 7.4, 7.5**
        """
        # Step 1: Discover CVs in empty directory
        discovered_cvs = cv_service.discover_cvs()
        
        # Step 2: Verify empty result
        assert len(discovered_cvs.cvs) == 0, "Empty directory should yield no CVs"
        assert discovered_cvs.total == 0, "Total count should be zero for empty directory"
    
    def test_corrupted_external_file_handling(self, cv_service, temp_data_dir):
        """
        Test that corrupted external files are handled gracefully.
        
        **Validates: Requirements 7.4, 7.5**
        """
        # Step 1: Create a corrupted JSON file
        cvs_dir = Path(temp_data_dir) / "cvs"
        cvs_dir.mkdir(parents=True, exist_ok=True)
        
        corrupted_file = cvs_dir / "corrupted.json"
        with open(corrupted_file, 'w') as f:
            f.write("{ invalid json content")
        
        # Step 2: Create a valid external CV
        valid_cv = {
            "id": str(uuid.uuid4()),
            "metadata": {"title": "Valid CV", "template_id": "default"},
            "personal_info": {"name": "Valid User", "contact": {}}
        }
        create_external_cv_file(temp_data_dir, valid_cv)
        
        # Step 3: Discover CVs (should handle corrupted file gracefully)
        discovered_cvs = cv_service.discover_cvs()
        
        # Step 4: Verify valid CV is discovered despite corrupted file
        discovered_ids = [cv.id for cv in discovered_cvs.cvs]
        assert valid_cv["id"] in discovered_ids, "Valid CV should be discovered despite corrupted file presence"
        
        # The corrupted file should be ignored (not cause the entire discovery to fail)
        assert len(discovered_cvs.cvs) >= 1, "At least the valid CV should be discovered"


# Additional unit tests for specific edge cases
class TestFileDiscoveryEdgeCases:
    """Unit tests for specific edge cases in file discovery."""
    
    def test_external_cv_with_minimal_data(self, cv_service, temp_data_dir):
        """Test discovery of external CV with minimal required data."""
        minimal_cv = {
            "id": str(uuid.uuid4()),
            "metadata": {"title": "Minimal External CV"},
            "personal_info": {"name": "Minimal User", "contact": {}}
        }
        
        create_external_cv_file(temp_data_dir, minimal_cv)
        
        discovered_cvs = cv_service.discover_cvs()
        discovered_ids = [cv.id for cv in discovered_cvs.cvs]
        
        assert minimal_cv["id"] in discovered_ids, "Minimal external CV should be discovered"
        
        # Verify it can be loaded properly
        loaded_cv = cv_service.get_cv(minimal_cv["id"])
        assert v2.cv_title(loaded_cv.cv) == "Minimal External CV"
        assert v2.full_name(loaded_cv.cv) == "Minimal User"
    
    def test_external_cv_with_unicode_content(self, cv_service, temp_data_dir):
        """Test discovery of external CV with Unicode characters."""
        unicode_cv = {
            "id": str(uuid.uuid4()),
            "metadata": {"title": "CV with Unicode: 测试 🚀"},
            "personal_info": {
                "name": "José María García-López",
                "title": "Développeur Senior",
                "contact": {"email": "josé@example.com"}
            },
            "summary": "Experienced engineer with expertise in 人工智能 and machine learning 🤖"
        }
        
        create_external_cv_file(temp_data_dir, unicode_cv)
        
        discovered_cvs = cv_service.discover_cvs()
        discovered_ids = [cv.id for cv in discovered_cvs.cvs]
        
        assert unicode_cv["id"] in discovered_ids, "Unicode external CV should be discovered"
        
        # Verify Unicode content is preserved
        loaded_cv = cv_service.get_cv(unicode_cv["id"])
        assert v2.cv_title(loaded_cv.cv) == "CV with Unicode: 测试 🚀"
        assert v2.full_name(loaded_cv.cv) == "José María García-López"
        assert "人工智能" in v2.summary_text(loaded_cv.cv)
        assert "🤖" in v2.summary_text(loaded_cv.cv)
    
    def test_external_cv_file_without_metadata_file(self, file_service, temp_data_dir):
        """Test that external CVs work even without metadata.json file."""
        external_cv = {
            "id": str(uuid.uuid4()),
            "metadata": {"title": "No Metadata File CV"},
            "personal_info": {"name": "No Metadata User", "contact": {}}
        }
        
        create_external_cv_file(temp_data_dir, external_cv)
        
        # Ensure no metadata.json exists
        metadata_file = Path(temp_data_dir) / "cvs" / "metadata.json"
        if metadata_file.exists():
            metadata_file.unlink()
        
        # Should still be able to list and load the CV
        cv_ids = file_service.list_cv_files()
        assert external_cv["id"] in cv_ids, "External CV should be listed even without metadata file"
        
        loaded_cv = file_service.load_cv(external_cv["id"])
        assert v2.cv_title(loaded_cv) == "No Metadata File CV"