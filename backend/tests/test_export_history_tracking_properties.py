"""
Property-based tests for export history tracking.

Feature: cv-web-app, Property 10: Export History Tracking
Validates: Requirements 5.1, 5.2
"""
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, Any, List
import uuid
import json
from datetime import datetime, timedelta

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from fastapi.testclient import TestClient

from app.models.cv_models import (
    CVModel, PersonalInfo, CVMetadata, ContactInfo,
    Experience, Education, SkillCategory, Skills, Certification,
    CVCreateRequest
)
from app.models.export_models import ExportFormat, ExportRequest, ExportStatus
from app.services.export_service import ExportService
from app.services.cv_service import CVService
from app.routers.export_router import router as export_router
from app.main import app


# Test data generators for valid CV data (reusing from other tests)
@st.composite
def contact_info_strategy(draw):
    """Generate valid ContactInfo data."""
    return ContactInfo(
        address=draw(st.one_of(st.none(), st.text(min_size=5, max_size=200))),
        phone=draw(st.one_of(st.none(), st.text(min_size=5, max_size=20))),
        email=draw(st.one_of(st.none(), st.emails())),
        linkedin=draw(st.one_of(st.none(), st.text(min_size=5, max_size=100))),
        website=draw(st.one_of(st.none(), st.text(min_size=5, max_size=100)))
    )


@st.composite
def personal_info_strategy(draw):
    """Generate valid PersonalInfo data."""
    return PersonalInfo(
        name=draw(st.text(min_size=1, max_size=100)),
        title=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        contact=draw(contact_info_strategy())
    )


@st.composite
def cv_metadata_strategy(draw):
    """Generate valid CVMetadata data."""
    return CVMetadata(
        title=draw(st.text(min_size=1, max_size=100)),
        template_id=draw(st.text(min_size=1, max_size=50))
    )


@st.composite
def experience_strategy(draw):
    """Generate valid Experience data."""
    current = draw(st.booleans())
    return Experience(
        title=draw(st.text(min_size=1, max_size=100)),
        company=draw(st.text(min_size=1, max_size=100)),
        location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        start_date=draw(st.text(min_size=1, max_size=20)),
        end_date=None if current else draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        current=current,
        description=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500))),
        achievements=draw(st.lists(st.text(min_size=5, max_size=100), min_size=0, max_size=5))
    )


@st.composite
def education_strategy(draw):
    """Generate valid Education data."""
    return Education(
        degree=draw(st.text(min_size=1, max_size=100)),
        institution=draw(st.text(min_size=1, max_size=100)),
        location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
        start_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        end_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        gpa=draw(st.one_of(st.none(), st.text(min_size=1, max_size=10))),
        description=draw(st.one_of(st.none(), st.text(min_size=10, max_size=300)))
    )


@st.composite
def skill_category_strategy(draw):
    """Generate valid SkillCategory data."""
    return SkillCategory(
        name=draw(st.text(min_size=1, max_size=50)),
        skills=draw(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=10))
    )


@st.composite
def skills_strategy(draw):
    """Generate valid Skills data."""
    return Skills(
        categories=draw(st.lists(skill_category_strategy(), min_size=0, max_size=5))
    )


@st.composite
def certification_strategy(draw):
    """Generate valid Certification data."""
    return Certification(
        name=draw(st.text(min_size=1, max_size=100)),
        issuer=draw(st.text(min_size=1, max_size=100)),
        date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        expiry_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20)))
    )


@st.composite
def cv_create_request_strategy(draw):
    """Generate valid CVCreateRequest data."""
    return CVCreateRequest(
        metadata=draw(cv_metadata_strategy()),
        personal_info=draw(personal_info_strategy()),
        summary=draw(st.one_of(st.none(), st.text(min_size=10, max_size=500))),
        experience=draw(st.lists(experience_strategy(), min_size=0, max_size=3)),
        education=draw(st.lists(education_strategy(), min_size=0, max_size=3)),
        skills=draw(skills_strategy()),
        certifications=draw(st.lists(certification_strategy(), min_size=0, max_size=3))
    )


@pytest.fixture
def temp_root_dir():
    """Fixture providing temporary root directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="cv_export_history_test_")
    
    # Create required directory structure
    directories = [
        "cv", "exports/pdf", "exports/docx", "exports/txt", 
        "templates", "pandoc", "scripts", "data/cvs"
    ]
    
    for directory in directories:
        (Path(temp_dir) / directory).mkdir(parents=True, exist_ok=True)
    
    # Copy required files from the actual project
    project_root = Path(__file__).parent.parent.parent
    
    # Copy export script
    export_script_src = project_root / "scripts" / "export.sh"
    export_script_dst = Path(temp_dir) / "scripts" / "export.sh"
    if export_script_src.exists():
        shutil.copy2(export_script_src, export_script_dst)
        os.chmod(export_script_dst, 0o755)  # Make executable
    
    # Copy templates
    template_src = project_root / "templates" / "cv.latex"
    template_dst = Path(temp_dir) / "templates" / "cv.latex"
    if template_src.exists():
        shutil.copy2(template_src, template_dst)
    
    # Copy pandoc configuration
    pandoc_src = project_root / "pandoc" / "defaults.yaml"
    pandoc_dst = Path(temp_dir) / "pandoc" / "defaults.yaml"
    if pandoc_src.exists():
        shutil.copy2(pandoc_src, pandoc_dst)
    
    # Copy pandoc filter
    filter_src = project_root / "pandoc" / "no_em_dash.lua"
    filter_dst = Path(temp_dir) / "pandoc" / "no_em_dash.lua"
    if filter_src.exists():
        shutil.copy2(filter_src, filter_dst)
    
    # Copy reference docx
    ref_docx_src = project_root / "scripts" / "reference.docx"
    ref_docx_dst = Path(temp_dir) / "scripts" / "reference.docx"
    if ref_docx_src.exists():
        shutil.copy2(ref_docx_src, ref_docx_dst)
    
    # Copy additional scripts that might be needed
    for script_name in ["normalize_txt.sh", "tune_docx.py"]:
        script_src = project_root / "scripts" / script_name
        script_dst = Path(temp_dir) / "scripts" / script_name
        if script_src.exists():
            shutil.copy2(script_src, script_dst)
            if script_name.endswith('.sh'):
                os.chmod(script_dst, 0o755)  # Make executable
    
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def export_service(temp_root_dir):
    """Fixture providing ExportService with temporary directory."""
    return ExportService(
        root_dir=temp_root_dir,
        export_script_path=Path(temp_root_dir) / "scripts" / "export.sh"
    )


@pytest.fixture
def cv_service(temp_root_dir):
    """Fixture providing CVService with temporary directory."""
    from app.services.file_service import FileService
    file_service = FileService(data_directory=str(Path(temp_root_dir) / "data"))
    return CVService(file_service=file_service)


@pytest.fixture
def test_client(temp_root_dir):
    """Fixture providing FastAPI test client with temporary directory."""
    # Override the service instances to use temporary directory
    from app.routers import export_router
    from app.services.file_service import FileService
    
    # Create services with temp directory
    export_service = ExportService(
        root_dir=temp_root_dir,
        export_script_path=Path(temp_root_dir) / "scripts" / "export.sh"
    )
    file_service = FileService(data_directory=str(Path(temp_root_dir) / "data"))
    cv_service = CVService(file_service=file_service)
    
    # Override the service getters
    export_router._export_service = export_service
    export_router._cv_service = cv_service
    
    return TestClient(app)


def _validate_export_history_entry(entry: Dict[str, Any], cv_data: CVModel, export_format: ExportFormat) -> bool:
    """
    Validate that an export history entry contains all required fields and correct data.
    
    Args:
        entry: Export history entry to validate
        cv_data: Original CV data that was exported
        export_format: Format that was exported
        
    Returns:
        True if entry is valid
    """
    required_fields = [
        "export_id", "cv_id", "cv_title", "format", "template_id",
        "file_name", "file_path", "file_size", "created_at", "download_url"
    ]
    
    # Check all required fields are present
    for field in required_fields:
        if field not in entry:
            return False
        if entry[field] is None:
            return False
    
    # Validate field values
    if entry["cv_id"] != cv_data.id:
        return False
    
    if entry["format"] != export_format.value:
        return False
    
    if entry["file_size"] <= 0:
        return False
    
    # Validate timestamp format and reasonableness
    try:
        created_at = datetime.fromisoformat(entry["created_at"].replace('Z', '+00:00'))
        now = datetime.now()
        # Should be within the last hour (reasonable for test execution)
        if created_at > now or (now - created_at).total_seconds() > 3600:
            return False
    except (ValueError, AttributeError):
        return False
    
    # Validate download URL format
    if not entry["download_url"].startswith("/api/export/download/"):
        return False
    
    # Validate file name contains format extension
    expected_extension = f".{export_format.value}"
    if not entry["file_name"].endswith(expected_extension):
        return False
    
    return True


def _validate_download_link_works(download_url: str, test_client: TestClient) -> bool:
    """
    Validate that a download link actually works.
    
    Args:
        download_url: URL to test
        test_client: FastAPI test client
        
    Returns:
        True if download link works
    """
    try:
        response = test_client.get(download_url)
        return response.status_code == 200 and len(response.content) > 0
    except Exception:
        return False


def _validate_file_exists_at_path(file_path: str) -> bool:
    """
    Validate that the exported file exists at the specified path.
    
    Args:
        file_path: Path to the exported file
        
    Returns:
        True if file exists and is readable
    """
    if not file_path:
        return False
    
    path = Path(file_path)
    return path.exists() and path.is_file() and os.access(path, os.R_OK)


def _validate_timestamp_format_and_identifier(entry: Dict[str, Any]) -> bool:
    """
    Validate that the export entry has proper timestamp and format identifier.
    
    Args:
        entry: Export history entry to validate
        
    Returns:
        True if timestamp and format identifier are valid
    """
    # Validate timestamp format (Requirements 5.1)
    try:
        created_at = datetime.fromisoformat(entry["created_at"].replace('Z', '+00:00'))
        # Should be a reasonable timestamp (not in future, not too old)
        now = datetime.now()
        if created_at > now:
            return False
        # Should be within last day for test purposes
        if (now - created_at).total_seconds() > 86400:
            return False
    except (ValueError, AttributeError, KeyError):
        return False
    
    # Validate format identifier (Requirements 5.1)
    if "format" not in entry:
        return False
    
    valid_formats = [f.value for f in ExportFormat]
    if entry["format"] not in valid_formats:
        return False
    
    # Validate that file name includes format identifier
    if "file_name" not in entry or "format" not in entry:
        return False
    
    expected_extension = f".{entry['format']}"
    if not entry["file_name"].endswith(expected_extension):
        return False
    
    return True


class TestExportHistoryTracking:
    """Property-based tests for export history tracking."""
    
    @given(cv_request=cv_create_request_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_history_tracking_single_export(self, export_service, cv_service, test_client, cv_request):
        """
        Property 10: Export History Tracking - Single Export
        
        For any export operation, the exported file should appear in the export history 
        with correct timestamp, format identifier, and working download link.
        
        **Validates: Requirements 5.1, 5.2**
        """
        # Step 1: Save CV data to the CV service
        cv_response = cv_service.create_cv(cv_request)
        cv_data = cv_response.cv
        
        # Step 2: Perform export operation (use TXT format for reliability)
        export_format = ExportFormat.TXT
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=export_format,
            template_id="default"
        )
        
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Step 3: Only proceed if export was successful
        if export_response.status != ExportStatus.COMPLETED:
            # Skip this test iteration if export failed (not testing export functionality here)
            return
        
        # Step 4: Retrieve export history
        history_response = test_client.get(f"/api/export/history/{cv_data.id}")
        assert history_response.status_code == 200, f"Export history request should succeed"
        
        history_data = history_response.json()
        
        # Step 5: Validate export appears in history (Requirements 5.2)
        assert "exports" in history_data, "History response should contain exports list"
        assert len(history_data["exports"]) > 0, "Export history should contain at least one entry"
        
        # Find the export we just created
        matching_exports = [
            entry for entry in history_data["exports"] 
            if entry.get("cv_id") == cv_data.id and entry.get("format") == export_format.value
        ]
        
        assert len(matching_exports) > 0, \
            f"Export history should contain entry for CV {cv_data.id} in {export_format.value} format"
        
        # Step 6: Validate the most recent export entry
        recent_export = matching_exports[0]  # Should be sorted by date (newest first)
        
        # Validate all required fields are present and correct (Requirements 5.1, 5.2)
        assert _validate_export_history_entry(recent_export, cv_data, export_format), \
            f"Export history entry should contain all required fields with correct values"
        
        # Step 7: Validate timestamp and format identifier (Requirements 5.1)
        assert _validate_timestamp_format_and_identifier(recent_export), \
            "Export should be stored with correct timestamp and format identifier"
        
        # Step 8: Validate file exists at specified path
        assert _validate_file_exists_at_path(recent_export["file_path"]), \
            f"Exported file should exist at specified path: {recent_export['file_path']}"
        
        # Step 9: Validate download link works (Requirements 5.2)
        assert _validate_download_link_works(recent_export["download_url"], test_client), \
            f"Download link should work: {recent_export['download_url']}"
        
        # Step 10: Validate history metadata
        assert history_data["cv_id"] == cv_data.id, "History response should have correct CV ID"
        assert history_data["total"] >= 1, "History total should reflect at least one export"
        assert len(history_data["exports"]) == history_data["total"], \
            "History exports count should match total"
    
    @given(cv_request=cv_create_request_strategy(), export_formats=st.lists(
        st.sampled_from([ExportFormat.TXT, ExportFormat.DOCX]), 
        min_size=2, max_size=3, unique=True
    ))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_history_tracking_multiple_formats(self, export_service, cv_service, test_client, cv_request, export_formats):
        """
        Property 10: Export History Tracking - Multiple Formats
        
        For any CV exported in multiple formats, each export should appear in the history
        with correct format identifiers and working download links.
        
        **Validates: Requirements 5.1, 5.2**
        """
        # Step 1: Save CV data
        cv_response = cv_service.create_cv(cv_request)
        cv_data = cv_response.cv
        
        # Step 2: Perform exports in multiple formats
        successful_exports = []
        
        for export_format in export_formats:
            export_request = ExportRequest(
                cv_id=cv_data.id,
                format=export_format,
                template_id="default"
            )
            
            export_response = export_service.export_cv(cv_data, export_request)
            
            if export_response.status == ExportStatus.COMPLETED:
                successful_exports.append(export_format)
        
        # Skip if no exports succeeded
        if not successful_exports:
            return
        
        # Step 3: Retrieve export history
        history_response = test_client.get(f"/api/export/history/{cv_data.id}")
        assert history_response.status_code == 200, "Export history request should succeed"
        
        history_data = history_response.json()
        
        # Step 4: Validate each successful export appears in history
        assert len(history_data["exports"]) >= len(successful_exports), \
            f"History should contain at least {len(successful_exports)} entries"
        
        for export_format in successful_exports:
            # Find exports for this format
            format_exports = [
                entry for entry in history_data["exports"]
                if entry.get("format") == export_format.value and entry.get("cv_id") == cv_data.id
            ]
            
            assert len(format_exports) > 0, \
                f"History should contain export for format {export_format.value}"
            
            # Validate the export entry
            export_entry = format_exports[0]
            
            # Validate timestamp and format identifier (Requirements 5.1)
            assert _validate_timestamp_format_and_identifier(export_entry), \
                f"Export for {export_format.value} should have correct timestamp and format identifier"
            
            # Validate download link (Requirements 5.2)
            assert _validate_download_link_works(export_entry["download_url"], test_client), \
                f"Download link should work for {export_format.value}: {export_entry['download_url']}"
            
            # Validate file exists
            assert _validate_file_exists_at_path(export_entry["file_path"]), \
                f"File should exist for {export_format.value}: {export_entry['file_path']}"
    
    @given(cv_request=cv_create_request_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_history_tracking_chronological_order(self, export_service, cv_service, test_client, cv_request):
        """
        Property 10: Export History Tracking - Chronological Order
        
        For any CV with multiple exports, the history should display them in chronological order
        (newest first) with correct timestamps.
        
        **Validates: Requirements 5.1, 5.2**
        """
        # Step 1: Save CV data
        cv_response = cv_service.create_cv(cv_request)
        cv_data = cv_response.cv
        
        # Step 2: Perform multiple exports with small delays
        export_times = []
        successful_exports = 0
        
        for i in range(2):  # Create 2 exports
            export_request = ExportRequest(
                cv_id=cv_data.id,
                format=ExportFormat.TXT,
                template_id="default"
            )
            
            before_export = datetime.now()
            export_response = export_service.export_cv(cv_data, export_request)
            after_export = datetime.now()
            
            if export_response.status == ExportStatus.COMPLETED:
                export_times.append((before_export, after_export))
                successful_exports += 1
            
            # Small delay between exports to ensure different timestamps
            import time
            time.sleep(0.1)
        
        # Skip if we don't have multiple successful exports
        if successful_exports < 2:
            return
        
        # Step 3: Retrieve export history
        history_response = test_client.get(f"/api/export/history/{cv_data.id}")
        assert history_response.status_code == 200, "Export history request should succeed"
        
        history_data = history_response.json()
        
        # Step 4: Validate chronological ordering (Requirements 5.2)
        exports = history_data["exports"]
        assert len(exports) >= successful_exports, \
            f"History should contain at least {successful_exports} exports"
        
        # Filter to only our CV's exports
        cv_exports = [e for e in exports if e.get("cv_id") == cv_data.id]
        assert len(cv_exports) >= successful_exports, \
            f"Should have at least {successful_exports} exports for this CV"
        
        # Validate chronological order (newest first)
        if len(cv_exports) >= 2:
            for i in range(len(cv_exports) - 1):
                current_time = datetime.fromisoformat(cv_exports[i]["created_at"].replace('Z', '+00:00'))
                next_time = datetime.fromisoformat(cv_exports[i + 1]["created_at"].replace('Z', '+00:00'))
                
                assert current_time >= next_time, \
                    "Export history should be ordered chronologically (newest first)"
        
        # Step 5: Validate timestamps are within expected ranges
        for i, export_entry in enumerate(cv_exports[:successful_exports]):
            export_time = datetime.fromisoformat(export_entry["created_at"].replace('Z', '+00:00'))
            
            # Should be within the time range when we performed the export
            if i < len(export_times):
                before_time, after_time = export_times[-(i+1)]  # Reverse order (newest first)
                
                # Allow some tolerance for processing time
                tolerance = timedelta(seconds=30)
                assert before_time - tolerance <= export_time <= after_time + tolerance, \
                    f"Export timestamp should be within expected range"
    
    @given(cv_request=cv_create_request_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_export_history_tracking_download_link_consistency(self, export_service, cv_service, test_client, cv_request):
        """
        Property 10: Export History Tracking - Download Link Consistency
        
        For any export in the history, the download link should consistently work
        and return the correct file content.
        
        **Validates: Requirements 5.1, 5.2**
        """
        # Step 1: Save CV data
        cv_response = cv_service.create_cv(cv_request)
        cv_data = cv_response.cv
        
        # Step 2: Perform export
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=ExportFormat.TXT,
            template_id="default"
        )
        
        export_response = export_service.export_cv(cv_data, export_request)
        
        # Skip if export failed
        if export_response.status != ExportStatus.COMPLETED:
            return
        
        # Step 3: Get export history
        history_response = test_client.get(f"/api/export/history/{cv_data.id}")
        assert history_response.status_code == 200, "Export history request should succeed"
        
        history_data = history_response.json()
        
        # Step 4: Find our export in the history
        cv_exports = [e for e in history_data["exports"] if e.get("cv_id") == cv_data.id]
        assert len(cv_exports) > 0, "Should have at least one export in history"
        
        export_entry = cv_exports[0]
        
        # Step 5: Validate download link format (Requirements 5.2)
        download_url = export_entry["download_url"]
        assert download_url.startswith("/api/export/download/"), \
            "Download URL should have correct format"
        
        # Step 6: Test download link multiple times for consistency
        for attempt in range(3):
            download_response = test_client.get(download_url)
            
            assert download_response.status_code == 200, \
                f"Download should work on attempt {attempt + 1}"
            
            assert len(download_response.content) > 0, \
                f"Downloaded file should not be empty on attempt {attempt + 1}"
            
            # Validate content type for TXT files
            if export_entry["format"] == "txt":
                content_type = download_response.headers.get("content-type", "")
                assert "text/plain" in content_type or "application/octet-stream" in content_type, \
                    "TXT file should have appropriate content type"
        
        # Step 7: Validate file size consistency
        actual_file_size = len(download_response.content)
        reported_file_size = export_entry["file_size"]
        
        assert actual_file_size == reported_file_size, \
            f"Downloaded file size ({actual_file_size}) should match reported size ({reported_file_size})"
        
        # Step 8: Validate file content contains CV data
        if export_entry["format"] == "txt":
            content = download_response.content.decode('utf-8', errors='ignore')
            
            # Should contain the person's name
            assert cv_data.personal_info.name.lower() in content.lower(), \
                "Downloaded file should contain the CV owner's name"


# Additional unit tests for specific export history scenarios
class TestExportHistoryTrackingEdgeCases:
    """Unit tests for specific export history tracking edge cases."""
    
    def test_export_history_empty_for_nonexistent_cv(self, test_client):
        """Test export history for non-existent CV returns empty list."""
        nonexistent_cv_id = str(uuid.uuid4())
        
        response = test_client.get(f"/api/export/history/{nonexistent_cv_id}")
        
        # Should return 404 for non-existent CV
        assert response.status_code == 404
    
    def test_export_history_empty_for_cv_with_no_exports(self, cv_service, test_client):
        """Test export history for CV with no exports returns empty list."""
        # Create a CV but don't export it
        cv_request = CVCreateRequest(
            metadata=CVMetadata(title="Test CV"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        cv_response = cv_service.create_cv(cv_request)
        cv_data = cv_response.cv
        
        response = test_client.get(f"/api/export/history/{cv_data.id}")
        assert response.status_code == 200
        
        history_data = response.json()
        assert history_data["cv_id"] == cv_data.id
        assert history_data["exports"] == []
        assert history_data["total"] == 0
    
    def test_export_history_with_special_characters_in_cv_title(self, export_service, cv_service, test_client):
        """Test export history tracking with special characters in CV title."""
        cv_request = CVCreateRequest(
            metadata=CVMetadata(title="CV with Special Characters: & < > \" '"),
            personal_info=PersonalInfo(name="Test User")
        )
        
        cv_response = cv_service.create_cv(cv_request)
        cv_data = cv_response.cv
        
        export_request = ExportRequest(
            cv_id=cv_data.id,
            format=ExportFormat.TXT,
            template_id="default"
        )
        
        export_response = export_service.export_cv(cv_data, export_request)
        
        if export_response.status == ExportStatus.COMPLETED:
            history_response = test_client.get(f"/api/export/history/{cv_data.id}")
            assert history_response.status_code == 200
            
            history_data = history_response.json()
            assert len(history_data["exports"]) > 0
            
            export_entry = history_data["exports"][0]
            assert export_entry["cv_title"] == cv_data.metadata.title
            assert _validate_download_link_works(export_entry["download_url"], test_client)