"""
CV Section Models

Pydantic models for flexible CV section structure. These models support
a section-based architecture where each section is an independent entity
with its own type, content, visibility, and position.
"""

from datetime import datetime
from typing import List, Optional, Union, Literal, Annotated
from uuid import UUID, uuid4
from enum import Enum

from pydantic import BaseModel, Field, field_validator, Discriminator


class SectionType(str, Enum):
    """Enumeration of available section types."""
    PERSONAL_INFO = "personal_info"
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    LANGUAGES = "languages"
    SOFTWARE = "software"
    CERTIFICATIONS = "certifications"
    ACCOMPLISHMENTS = "accomplishments"
    AFFILIATIONS = "affiliations"
    INTERESTS = "interests"
    WEBSITES = "websites"
    CUSTOM = "custom"


# Content Models by Type

class ListItem(BaseModel):
    """A single item in a list section."""
    text: str = Field(..., min_length=1, description="Item text is required")


class ListSectionContent(BaseModel):
    """Content for list-based sections (Skills, Languages, Software, Interests)."""
    content_type: Literal["list"] = "list"
    items: List[ListItem] = Field(default_factory=list)


class ExperienceEntry(BaseModel):
    """A single work experience entry."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(..., min_length=1, description="Job title is required")
    company: Optional[str] = Field(None, description="Company name")
    location: Optional[str] = None
    start_date: Optional[str] = Field(None, description="Start date")
    end_date: Optional[str] = None
    current: bool = Field(default=False, description="Currently employed")
    description: Optional[str] = None
    achievements: List[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    """A single education entry."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    degree: str = Field(..., min_length=1, description="Degree is required")
    institution: str = Field(..., min_length=1, description="Institution is required")
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    gpa: Optional[str] = None
    description: Optional[str] = None


class CertificationEntry(BaseModel):
    """A single certification entry."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, description="Certification name is required")
    issuer: str = Field(..., min_length=1, description="Issuer is required")
    date: Optional[str] = None
    expiry_date: Optional[str] = None
    credential_id: Optional[str] = None


class StructuredSectionContent(BaseModel):
    """Content for structured entry sections (Experience, Education, Certifications)."""
    content_type: Literal["structured"] = "structured"
    entries: List[Union[ExperienceEntry, EducationEntry, CertificationEntry]] = Field(
        default_factory=list
    )


class FreeTextSectionContent(BaseModel):
    """Content for free-text sections (Summary, Custom sections)."""
    content_type: Literal["free_text"] = "free_text"
    text: str = Field(default="", description="Free-form text content")


class PersonalInfoContent(BaseModel):
    """Content for personal information section."""
    content_type: Literal["personal"] = "personal"
    cv_title: Optional[str] = Field(None, description="CV title for identification")
    full_name: str = Field(default="", description="Full name")
    email: str = Field(default="", description="Email address")
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    website: Optional[str] = None
    title: Optional[str] = Field(None, description="Professional title")


# Section Base and Main Model

class SectionBase(BaseModel):
    """Base model for all section types."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: SectionType
    title: str = Field(..., min_length=1, description="Section title is required")
    visible: bool = Field(default=True, description="Whether section appears in exports")
    order: int = Field(..., ge=0, description="Position in section list (0-indexed)")


class Section(SectionBase):
    """
    A section in a CV with type-specific content.
    
    Uses discriminated union for content based on section type.
    """
    content: Annotated[
        Union[
            PersonalInfoContent,
            FreeTextSectionContent,
            ListSectionContent,
            StructuredSectionContent
        ],
        Field(discriminator='content_type')
    ] = Field(..., description="Section content matching the section type")
    
    @property
    def is_core(self) -> bool:
        """
        Core sections cannot be removed.
        Currently only Personal Information is core.
        """
        return self.type == SectionType.PERSONAL_INFO
    
    @property
    def content_structure(self) -> Literal["personal", "free_text", "list", "structured"]:
        """
        Determine content structure category based on section type.
        Used for validation and rendering.
        """
        if self.type == SectionType.PERSONAL_INFO:
            return "personal"
        elif self.type in [
            SectionType.SKILLS,
            SectionType.LANGUAGES,
            SectionType.SOFTWARE,
            SectionType.INTERESTS
        ]:
            return "list"
        elif self.type in [
            SectionType.EXPERIENCE,
            SectionType.EDUCATION,
            SectionType.CERTIFICATIONS
        ]:
            return "structured"
        else:
            return "free_text"
    
    @field_validator('content')
    @classmethod
    def validate_content_matches_type(cls, v, info):
        """Validate that content structure matches section type."""
        if 'type' not in info.data:
            return v
        
        section_type = info.data['type']
        
        # Define expected content types for each section type
        if section_type == SectionType.PERSONAL_INFO:
            if not isinstance(v, PersonalInfoContent):
                raise ValueError(
                    f"Personal info section must have PersonalInfoContent, got {type(v).__name__}"
                )
        elif section_type in [
            SectionType.SKILLS,
            SectionType.LANGUAGES,
            SectionType.SOFTWARE,
            SectionType.INTERESTS
        ]:
            if not isinstance(v, ListSectionContent):
                raise ValueError(
                    f"List section must have ListSectionContent, got {type(v).__name__}"
                )
        elif section_type in [
            SectionType.EXPERIENCE,
            SectionType.EDUCATION,
            SectionType.CERTIFICATIONS
        ]:
            if not isinstance(v, StructuredSectionContent):
                raise ValueError(
                    f"Structured section must have StructuredSectionContent, got {type(v).__name__}"
                )
        elif section_type in [SectionType.SUMMARY, SectionType.CUSTOM]:
            if not isinstance(v, FreeTextSectionContent):
                raise ValueError(
                    f"Free-text section must have FreeTextSectionContent, got {type(v).__name__}"
                )
        
        return v


# Request/Response Models

class AddPredefinedSectionRequest(BaseModel):
    """Request to add a predefined section type."""
    section_type: SectionType = Field(..., description="Type of section to add")


class AddCustomSectionRequest(BaseModel):
    """Request to add a custom section."""
    title: str = Field(..., min_length=1, description="Custom section title")
    
    @field_validator('title')
    @classmethod
    def validate_title_not_whitespace(cls, v):
        """Ensure title is not just whitespace."""
        if not v or v.strip() == "":
            raise ValueError("Custom section title cannot be empty or whitespace")
        return v.strip()


class ReorderSectionsRequest(BaseModel):
    """Request to reorder sections."""
    section_ids: List[str] = Field(..., min_items=1, description="Ordered list of section IDs")


class ToggleVisibilityRequest(BaseModel):
    """Request to toggle section visibility."""
    visible: bool = Field(..., description="New visibility state")


class SectionResponse(BaseModel):
    """Response containing a single section."""
    section: Section
    message: Optional[str] = None
