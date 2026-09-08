"""
CV Data Models

Pydantic models for CV data structure with validation for required fields
and data integrity. These models define the core data structure for CV
documents and ensure data consistency across the application.
"""

from datetime import datetime
from typing import List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator

# Import typography models
from .typography_models import TypographyConfig
# Import section models
from .cv_section_models import Section, SectionType


class ContactInfo(BaseModel):
    """Contact information for personal details."""
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
    website: Optional[str] = None


class PersonalInfo(BaseModel):
    """Personal information section of CV."""
    name: str = Field(default="", description="Full name")
    title: Optional[str] = Field(None, description="Professional title or position")
    contact: ContactInfo = Field(default_factory=ContactInfo)


class CVMetadata(BaseModel):
    """Metadata for CV document."""
    title: str = Field(default="Untitled CV", description="CV title")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    template_id: str = Field(default="default", description="Template identifier")


class Experience(BaseModel):
    """Work experience entry."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(..., min_length=1, description="Job title is required")
    company: Optional[str] = Field(None, description="Company name")
    location: Optional[str] = None
    start_date: Optional[str] = Field(None, description="Start date")
    end_date: Optional[str] = None
    current: bool = Field(default=False, description="Currently employed at this position")
    description: Optional[str] = None
    achievements: List[str] = Field(default_factory=list)

    @validator('end_date')
    def validate_end_date(cls, v, values):
        """Validate that end_date is not required if current is True."""
        if values.get('current') is True and v is not None:
            # Allow end_date to be set even if current is True (for flexibility)
            pass
        return v


class Education(BaseModel):
    """Education entry."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    degree: str = Field(..., min_length=1, description="Degree is required")
    institution: str = Field(..., min_length=1, description="Institution name is required")
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    gpa: Optional[str] = None
    description: Optional[str] = None


class SkillCategory(BaseModel):
    """Skill category with associated skills."""
    name: str = Field(..., min_length=1, description="Category name is required")
    skills: List[str] = Field(default_factory=list)


class Skills(BaseModel):
    """Skills section with categorized skills."""
    categories: List[SkillCategory] = Field(default_factory=list)


class Certification(BaseModel):
    """Certification entry."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, description="Certification name is required")
    issuer: str = Field(..., min_length=1, description="Issuer is required")
    date: Optional[str] = None
    expiry_date: Optional[str] = None


class CVModel(BaseModel):
    """Complete CV data model (Legacy - Version 1)."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    metadata: CVMetadata
    personal_info: PersonalInfo
    summary: Optional[str] = None
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    skills: Skills = Field(default_factory=Skills)
    certifications: List[Certification] = Field(default_factory=list)
    typography: Optional[TypographyConfig] = Field(default=None, description="Typography configuration for this CV")

    class Config:
        """Pydantic configuration."""
        # Allow population by field name or alias
        populate_by_name = True
        # Generate example schema
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "metadata": {
                    "title": "Software Engineer CV",
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                    "template_id": "default"
                },
                "personal_info": {
                    "name": "John Doe",
                    "title": "Senior Software Engineer",
                    "contact": {
                        "address": "123 Main St, City, State 12345",
                        "phone": "+1-555-123-4567",
                        "email": "john.doe@example.com",
                        "linkedin": "linkedin.com/in/johndoe",
                        "website": "https://johndoe.dev"
                    }
                },
                "summary": "Experienced software engineer with expertise in web development.",
                "experience": [
                    {
                        "id": "exp-1",
                        "title": "Senior Software Engineer",
                        "company": "Tech Corp",
                        "location": "San Francisco, CA",
                        "start_date": "2020-01",
                        "end_date": None,
                        "current": True,
                        "description": "Lead development of web applications",
                        "achievements": ["Improved performance by 50%", "Led team of 5 developers"]
                    }
                ],
                "education": [
                    {
                        "id": "edu-1",
                        "degree": "Bachelor of Science in Computer Science",
                        "institution": "University of Technology",
                        "location": "Boston, MA",
                        "start_date": "2016-09",
                        "end_date": "2020-05",
                        "gpa": "3.8",
                        "description": "Focused on software engineering and algorithms"
                    }
                ],
                "skills": {
                    "categories": [
                        {
                            "name": "Programming Languages",
                            "skills": ["Python", "JavaScript", "TypeScript", "Java"]
                        },
                        {
                            "name": "Frameworks",
                            "skills": ["React", "Vue.js", "FastAPI", "Django"]
                        }
                    ]
                },
                "certifications": [
                    {
                        "id": "cert-1",
                        "name": "AWS Certified Solutions Architect",
                        "issuer": "Amazon Web Services",
                        "date": "2023-06",
                        "expiry_date": "2026-06"
                    }
                ]
            }
        }


class CVModelV2(BaseModel):
    """
    Complete CV data model with flexible section structure (Version 2).
    
    This model supports user-configurable sections with custom ordering,
    visibility control, and various content types.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = Field(None, description="User who owns this CV")
    sections: List[Section] = Field(default_factory=list, description="Ordered list of CV sections")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    version: int = Field(default=2, description="CV format version (2 = flexible sections)")
    typography: Optional[TypographyConfig] = Field(default=None, description="Typography configuration")
    applied_template_id: Optional[str] = Field(default=None, description="ID of the last applied typography template")
    
    def get_visible_sections(self) -> List[Section]:
        """
        Return sections that should appear in exports.
        Sections are sorted by their order field.
        """
        return sorted(
            [s for s in self.sections if s.visible],
            key=lambda s: s.order
        )
    
    def get_section_by_id(self, section_id: str) -> Optional[Section]:
        """Find a section by its ID."""
        return next((s for s in self.sections if s.id == section_id), None)
    
    def get_section_by_type(self, section_type: SectionType) -> Optional[Section]:
        """
        Find a section by its type.
        Useful for predefined sections where only one instance should exist.
        """
        return next((s for s in self.sections if s.type == section_type), None)
    
    class Config:
        """Pydantic configuration."""
        populate_by_name = True


# Request/Response models for API endpoints
class CVCreateRequest(BaseModel):
    """Request model for creating a new CV."""
    metadata: CVMetadata = Field(default_factory=CVMetadata)
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: Optional[str] = None
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    skills: Skills = Field(default_factory=Skills)
    certifications: List[Certification] = Field(default_factory=list)
    typography: Optional[TypographyConfig] = None


class CVUpdateRequest(BaseModel):
    """Request model for updating an existing CV."""
    metadata: Optional[CVMetadata] = None
    personal_info: Optional[PersonalInfo] = None
    summary: Optional[str] = None
    experience: Optional[List[Experience]] = None
    education: Optional[List[Education]] = None
    skills: Optional[Skills] = None
    certifications: Optional[List[Certification]] = None
    typography: Optional[TypographyConfig] = None


class CVUpdateRequestV2(BaseModel):
    """Request model for updating a V2 CV with sections."""
    sections: Optional[List[Section]] = None
    typography: Optional[TypographyConfig] = None


class CVListResponse(BaseModel):
    """Response model for CV list endpoint."""
    cvs: List[CVModelV2]
    total: int


class CVResponse(BaseModel):
    """Response model for single CV operations."""
    cv: CVModelV2
    message: Optional[str] = None