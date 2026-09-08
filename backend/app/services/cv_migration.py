"""
CV Migration

Converts legacy V1 CV documents (fixed metadata/personal_info/experience/...
structure) into the V2 flexible-section model used by the API and exports.
"""

import logging
from uuid import uuid4

from ..models.cv_models import CVModel, CVModelV2
from ..models.cv_section_models import (
    Section,
    SectionType,
    PersonalInfoContent,
    FreeTextSectionContent,
    StructuredSectionContent,
    ListSectionContent,
    ListItem,
    ExperienceEntry,
    EducationEntry,
    CertificationEntry,
)

logger = logging.getLogger(__name__)


def migrate_v1_to_v2(cv_data: CVModel) -> CVModelV2:
    """
    Convert a V1 CVModel into an equivalent V2 CVModelV2 with sections.

    The CV id is preserved so links and files stay valid. Empty V1 areas are
    skipped rather than producing empty sections.
    """
    sections = []
    order = 0

    contact = cv_data.personal_info.contact
    sections.append(Section(
        id=str(uuid4()),
        type=SectionType.PERSONAL_INFO,
        title="Personal Information",
        visible=True,
        order=order,
        content=PersonalInfoContent(
            content_type="personal",
            cv_title=cv_data.metadata.title or None,
            full_name=cv_data.personal_info.name or "",
            email=contact.email or "",
            phone=contact.phone or None,
            location=contact.address or None,
            linkedin=contact.linkedin or None,
            website=contact.website or None,
            title=cv_data.personal_info.title or None,
        )
    ))
    order += 1

    if cv_data.summary and cv_data.summary.strip():
        sections.append(Section(
            id=str(uuid4()),
            type=SectionType.SUMMARY,
            title="Professional Summary",
            visible=True,
            order=order,
            content=FreeTextSectionContent(
                content_type="free_text",
                text=cv_data.summary
            )
        ))
        order += 1

    experience_entries = [
        ExperienceEntry(
            id=exp.id or str(uuid4()),
            title=exp.title,
            company=exp.company,
            location=exp.location or None,
            start_date=exp.start_date or None,
            end_date=exp.end_date or None,
            current=exp.current,
            description=exp.description or None,
            achievements=exp.achievements or [],
        )
        for exp in cv_data.experience
        if exp.title
    ]
    if experience_entries:
        sections.append(Section(
            id=str(uuid4()),
            type=SectionType.EXPERIENCE,
            title="Work Experience",
            visible=True,
            order=order,
            content=StructuredSectionContent(
                content_type="structured",
                entries=experience_entries
            )
        ))
        order += 1

    education_entries = [
        EducationEntry(
            id=edu.id or str(uuid4()),
            degree=edu.degree,
            institution=edu.institution,
            location=edu.location or None,
            start_date=edu.start_date or None,
            end_date=edu.end_date or None,
            gpa=edu.gpa or None,
            description=edu.description or None,
        )
        for edu in cv_data.education
        if edu.degree and edu.institution
    ]
    if education_entries:
        sections.append(Section(
            id=str(uuid4()),
            type=SectionType.EDUCATION,
            title="Education",
            visible=True,
            order=order,
            content=StructuredSectionContent(
                content_type="structured",
                entries=education_entries
            )
        ))
        order += 1

    skill_items = []
    for category in cv_data.skills.categories:
        for skill in category.skills or []:
            if skill and skill.strip():
                skill_items.append(ListItem(text=skill))
    if skill_items:
        sections.append(Section(
            id=str(uuid4()),
            type=SectionType.SKILLS,
            title="Skills",
            visible=True,
            order=order,
            content=ListSectionContent(
                content_type="list",
                items=skill_items
            )
        ))
        order += 1

    certification_entries = [
        CertificationEntry(
            id=cert.id or str(uuid4()),
            name=cert.name,
            issuer=cert.issuer,
            date=cert.date or None,
            expiry_date=cert.expiry_date,
            credential_id=getattr(cert, "credential_id", None),
        )
        for cert in cv_data.certifications
        if cert.name and cert.issuer
    ]
    if certification_entries:
        sections.append(Section(
            id=str(uuid4()),
            type=SectionType.CERTIFICATIONS,
            title="Certifications",
            visible=True,
            order=order,
            content=StructuredSectionContent(
                content_type="structured",
                entries=certification_entries
            )
        ))
        order += 1

    cv_v2 = CVModelV2(
        id=cv_data.id,
        sections=sections,
        created_at=cv_data.metadata.created_at,
        updated_at=cv_data.metadata.updated_at,
        version=2,
        typography=cv_data.typography,
    )

    logger.info(f"Migrated CV {cv_data.id} from V1 to V2 with {len(sections)} sections")
    return cv_v2
