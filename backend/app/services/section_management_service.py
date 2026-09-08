"""
Section Management Service

Service layer for managing CV sections including adding, removing, reordering,
and toggling visibility. Implements business logic and validation for section
operations.
"""

from datetime import datetime
from typing import List
from uuid import uuid4

from ..models.cv_models import CVModelV2
from ..models.cv_section_models import (
    Section,
    SectionType,
    PersonalInfoContent,
    FreeTextSectionContent,
    ListSectionContent,
    StructuredSectionContent,
)


class SectionManagementService:
    """
    Service for managing CV sections.
    
    Provides operations for:
    - Adding predefined and custom sections
    - Removing optional sections
    - Reordering sections
    - Toggling section visibility
    """
    
    def add_predefined_section(
        self, 
        cv: CVModelV2, 
        section_type: SectionType
    ) -> Section:
        """
        Add a predefined section to the CV.
        
        Args:
            cv: The CV to add the section to
            section_type: Type of predefined section to add
            
        Returns:
            The newly created section
            
        Raises:
            ValueError: If section type already exists in CV
        """
        # Check for duplicates
        if cv.get_section_by_type(section_type):
            raise ValueError(f"Section type {section_type.value} already exists")
        
        # Create section with appropriate content structure
        content = self._create_default_content(section_type)
        title = self._get_default_title(section_type)
        order = self._get_next_order(cv)
        
        section = Section(
            id=str(uuid4()),
            type=section_type,
            title=title,
            content=content,
            order=order,
            visible=True
        )
        
        cv.sections.append(section)
        cv.updated_at = datetime.now()
        return section
    
    def add_custom_section(
        self,
        cv: CVModelV2,
        title: str
    ) -> Section:
        """
        Add a custom section with user-defined title.
        
        Args:
            cv: The CV to add the section to
            title: Custom title for the section
            
        Returns:
            The newly created section
            
        Raises:
            ValueError: If title is empty or whitespace only
        """
        # Validate title
        if not title or title.strip() == "":
            raise ValueError("Custom section title cannot be empty")
        
        order = self._get_next_order(cv)
        section = Section(
            id=str(uuid4()),
            type=SectionType.CUSTOM,
            title=title.strip(),
            content=FreeTextSectionContent(text=""),
            order=order,
            visible=True
        )
        
        cv.sections.append(section)
        cv.updated_at = datetime.now()
        return section
    
    def remove_section(
        self,
        cv: CVModelV2,
        section_id: str
    ) -> None:
        """
        Remove a section from the CV.
        
        Args:
            cv: The CV to remove the section from
            section_id: ID of the section to remove
            
        Raises:
            ValueError: If section is core or not found
        """
        section = cv.get_section_by_id(section_id)
        if not section:
            raise ValueError(f"Section {section_id} not found")
        
        if section.is_core:
            raise ValueError("Cannot remove core section")
        
        cv.sections.remove(section)
        self._reindex_order(cv)
        cv.updated_at = datetime.now()
    
    def reorder_sections(
        self,
        cv: CVModelV2,
        section_order: List[str]
    ) -> None:
        """
        Update section order based on provided list of section IDs.
        
        Args:
            cv: The CV to reorder sections in
            section_order: Ordered list of section IDs
            
        Raises:
            ValueError: If section IDs don't match CV sections
        """
        # Validate all section IDs exist and match
        existing_ids = {s.id for s in cv.sections}
        provided_ids = set(section_order)
        
        if existing_ids != provided_ids:
            raise ValueError("Section IDs do not match CV sections")
        
        # Update order field for each section
        for index, section_id in enumerate(section_order):
            section = cv.get_section_by_id(section_id)
            if section:
                section.order = index
        
        cv.updated_at = datetime.now()
    
    def toggle_visibility(
        self,
        cv: CVModelV2,
        section_id: str,
        visible: bool
    ) -> None:
        """
        Toggle section visibility.
        
        Args:
            cv: The CV containing the section
            section_id: ID of the section to toggle
            visible: New visibility state
            
        Raises:
            ValueError: If section not found
        """
        section = cv.get_section_by_id(section_id)
        if not section:
            raise ValueError(f"Section {section_id} not found")
        
        section.visible = visible
        cv.updated_at = datetime.now()
    
    def _get_next_order(self, cv: CVModelV2) -> int:
        """
        Get the next order value for a new section.
        
        Args:
            cv: The CV to get the next order for
            
        Returns:
            Next available order value
        """
        if not cv.sections:
            return 0
        return max(s.order for s in cv.sections) + 1
    
    def _reindex_order(self, cv: CVModelV2) -> None:
        """
        Reindex section order after removal to ensure consecutive values.
        
        Args:
            cv: The CV to reindex sections for
        """
        sorted_sections = sorted(cv.sections, key=lambda s: s.order)
        for index, section in enumerate(sorted_sections):
            section.order = index
    
    def _create_default_content(self, section_type: SectionType):
        """
        Create empty content structure for section type.
        
        Args:
            section_type: Type of section to create content for
            
        Returns:
            Appropriate content model instance
        """
        if section_type == SectionType.PERSONAL_INFO:
            return PersonalInfoContent(
                cv_title=None,
                full_name="Your Name",
                email="your.email@example.com"
            )
        elif section_type in [
            SectionType.SKILLS,
            SectionType.LANGUAGES,
            SectionType.SOFTWARE,
            SectionType.INTERESTS
        ]:
            return ListSectionContent(items=[])
        elif section_type in [
            SectionType.EXPERIENCE,
            SectionType.EDUCATION,
            SectionType.CERTIFICATIONS
        ]:
            return StructuredSectionContent(entries=[])
        else:
            return FreeTextSectionContent(text="")
    
    def _get_default_title(self, section_type: SectionType) -> str:
        """
        Get default title for predefined section types.
        
        Args:
            section_type: Type of section
            
        Returns:
            Default title string
        """
        titles = {
            SectionType.PERSONAL_INFO: "Personal Information",
            SectionType.SUMMARY: "Professional Summary",
            SectionType.EXPERIENCE: "Work Experience",
            SectionType.EDUCATION: "Education",
            SectionType.SKILLS: "Skills",
            SectionType.LANGUAGES: "Languages",
            SectionType.SOFTWARE: "Software & Tools",
            SectionType.CERTIFICATIONS: "Certifications",
            SectionType.ACCOMPLISHMENTS: "Accomplishments",
            SectionType.AFFILIATIONS: "Professional Affiliations",
            SectionType.INTERESTS: "Interests",
            SectionType.WEBSITES: "Websites & Portfolios"
        }
        return titles.get(section_type, section_type.value.replace("_", " ").title())
