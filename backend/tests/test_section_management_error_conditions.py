"""
Unit Tests for Section Management Error Conditions

Tests error handling for:
- Duplicate section error
- Empty title error
- Core section removal error
- Section not found error
- Invalid reorder error

Validates: Requirements 3.2, 2.3, 1.4
"""

import pytest

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import SectionType, Section, FreeTextSectionContent
from app.services.section_management_service import SectionManagementService


class TestDuplicateSectionError:
    """Test duplicate section error handling."""
    
    def test_duplicate_predefined_section_raises_error(self):
        """
        Test that adding a duplicate predefined section raises ValueError.
        Validates: Requirements 1.4
        """
        service = SectionManagementService()
        cv = CVModelV2(id="test-cv", sections=[])
        
        # Add section first time
        service.add_predefined_section(cv, SectionType.SKILLS)
        
        # Attempt to add same section type again
        with pytest.raises(ValueError) as exc_info:
            service.add_predefined_section(cv, SectionType.SKILLS)
        
        assert "already exists" in str(exc_info.value).lower()
        assert len(cv.sections) == 1


class TestEmptyTitleError:
    """Test empty title error handling."""
    
    def test_empty_string_title_raises_error(self):
        """
        Test that empty string title raises ValueError.
        Validates: Requirements 2.3
        """
        service = SectionManagementService()
        cv = CVModelV2(id="test-cv", sections=[])
        
        with pytest.raises(ValueError) as exc_info:
            service.add_custom_section(cv, "")
        
        assert "empty" in str(exc_info.value).lower()
        assert len(cv.sections) == 0
    
    def test_whitespace_only_title_raises_error(self):
        """
        Test that whitespace-only title raises ValueError.
        Validates: Requirements 2.3
        """
        service = SectionManagementService()
        cv = CVModelV2(id="test-cv", sections=[])
        
        with pytest.raises(ValueError) as exc_info:
            service.add_custom_section(cv, "   ")
        
        assert "empty" in str(exc_info.value).lower()
        assert len(cv.sections) == 0
    
    def test_tab_and_newline_title_raises_error(self):
        """
        Test that title with only tabs and newlines raises ValueError.
        Validates: Requirements 2.3
        """
        service = SectionManagementService()
        cv = CVModelV2(id="test-cv", sections=[])
        
        with pytest.raises(ValueError) as exc_info:
            service.add_custom_section(cv, "\t\n\r")
        
        assert "empty" in str(exc_info.value).lower()
        assert len(cv.sections) == 0


class TestCoreSectionRemovalError:
    """Test core section removal error handling."""
    
    def test_removing_personal_info_raises_error(self):
        """
        Test that removing Personal Info section raises ValueError.
        Validates: Requirements 3.2
        """
        service = SectionManagementService()
        cv = CVModelV2(id="test-cv", sections=[])
        
        # Add core section
        section = service.add_predefined_section(cv, SectionType.PERSONAL_INFO)
        
        # Attempt to remove core section
        with pytest.raises(ValueError) as exc_info:
            service.remove_section(cv, section.id)
        
        assert "core" in str(exc_info.value).lower()
        assert section in cv.sections
        assert len(cv.sections) == 1


class TestSectionNotFoundError:
    """Test section not found error handling."""
    
    def test_removing_nonexistent_section_raises_error(self):
        """
        Test that removing a non-existent section raises ValueError.
        """
        service = SectionManagementService()
        cv = CVModelV2(id="test-cv", sections=[])
        
        with pytest.raises(ValueError) as exc_info:
            service.remove_section(cv, "nonexistent-id")
        
        assert "not found" in str(exc_info.value).lower()
    
    def test_toggling_visibility_of_nonexistent_section_raises_error(self):
        """
        Test that toggling visibility of non-existent section raises ValueError.
        """
        service = SectionManagementService()
        cv = CVModelV2(id="test-cv", sections=[])
        
        with pytest.raises(ValueError) as exc_info:
            service.toggle_visibility(cv, "nonexistent-id", False)
        
        assert "not found" in str(exc_info.value).lower()


class TestInvalidReorderError:
    """Test invalid reorder error handling."""
    
    def test_reorder_with_missing_section_id_raises_error(self):
        """
        Test that reordering with missing section ID raises ValueError.
        """
        service = SectionManagementService()
        cv = CVModelV2(id="test-cv", sections=[])
        
        # Add sections
        section1 = service.add_custom_section(cv, "Section 1")
        section2 = service.add_custom_section(cv, "Section 2")
        
        # Attempt to reorder with only one ID (missing section2)
        with pytest.raises(ValueError) as exc_info:
            service.reorder_sections(cv, [section1.id])
        
        assert "do not match" in str(exc_info.value).lower()
    
    def test_reorder_with_extra_section_id_raises_error(self):
        """
        Test that reordering with extra section ID raises ValueError.
        """
        service = SectionManagementService()
        cv = CVModelV2(id="test-cv", sections=[])
        
        # Add section
        section1 = service.add_custom_section(cv, "Section 1")
        
        # Attempt to reorder with extra ID
        with pytest.raises(ValueError) as exc_info:
            service.reorder_sections(cv, [section1.id, "extra-id"])
        
        assert "do not match" in str(exc_info.value).lower()
    
    def test_reorder_with_wrong_section_ids_raises_error(self):
        """
        Test that reordering with completely wrong IDs raises ValueError.
        """
        service = SectionManagementService()
        cv = CVModelV2(id="test-cv", sections=[])
        
        # Add sections
        service.add_custom_section(cv, "Section 1")
        service.add_custom_section(cv, "Section 2")
        
        # Attempt to reorder with wrong IDs
        with pytest.raises(ValueError) as exc_info:
            service.reorder_sections(cv, ["wrong-id-1", "wrong-id-2"])
        
        assert "do not match" in str(exc_info.value).lower()
