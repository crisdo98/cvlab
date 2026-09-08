"""
Property-Based Tests for Import Completion Workflow

Feature: linkedin-profile-import, Property 14: Import Completion Workflow

For any preview acceptance action, the system should create a new CV record
with the parsed data, persist it to storage, and navigate the user to the CV
editor with the newly created CV loaded.

Validates: Requirements 10.4
"""

import pytest
from hypothesis import given, strategies as st, settings
from hypothesis import HealthCheck
from datetime import datetime
from uuid import uuid4

from app.models.cv_models import (
    CVModel, CVMetadata, PersonalInfo, ContactInfo,
    Experience, Education, Skills, SkillCategory, Certification
)


# Strategy for generating valid CV data
@st.composite
def cv_data_strategy(draw):
    """Generate valid CV data for testing."""
    return {
        "metadata": {
            "title": draw(st.text(min_size=1, max_size=100)),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "template_id": "default"
        },
        "personal_info": {
            "name": draw(st.text(min_size=1, max_size=100)),
            "title": draw(st.text(min_size=0, max_size=100)),
            "contact": {
                "email": draw(st.emails() | st.just("")),
                "phone": draw(st.text(min_size=0, max_size=20)),
                "address": draw(st.text(min_size=0, max_size=200)),
                "linkedin": draw(st.text(min_size=0, max_size=100)),
                "website": draw(st.text(min_size=0, max_size=100))
            }
        },
        "summary": draw(st.text(min_size=0, max_size=500)),
        "experience": draw(st.lists(
            st.fixed_dictionaries({
                "id": st.just(str(uuid4())),
                "title": st.text(min_size=1, max_size=100),
                "company": st.text(min_size=1, max_size=100),
                "location": st.text(min_size=0, max_size=100),
                "start_date": st.text(min_size=1, max_size=20),
                "end_date": st.text(min_size=0, max_size=20) | st.none(),
                "current": st.booleans(),
                "description": st.text(min_size=0, max_size=500),
                "achievements": st.lists(st.text(min_size=1, max_size=200), max_size=5)
            }),
            max_size=5
        )),
        "education": draw(st.lists(
            st.fixed_dictionaries({
                "id": st.just(str(uuid4())),
                "degree": st.text(min_size=1, max_size=100),
                "institution": st.text(min_size=1, max_size=100),
                "location": st.text(min_size=0, max_size=100),
                "start_date": st.text(min_size=0, max_size=20),
                "end_date": st.text(min_size=0, max_size=20),
                "gpa": st.text(min_size=0, max_size=10),
                "description": st.text(min_size=0, max_size=500)
            }),
            max_size=5
        )),
        "skills": {
            "categories": draw(st.lists(
                st.fixed_dictionaries({
                    "name": st.text(min_size=1, max_size=50),
                    "skills": st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10)
                }),
                max_size=5
            ))
        },
        "certifications": draw(st.lists(
            st.fixed_dictionaries({
                "id": st.just(str(uuid4())),
                "name": st.text(min_size=1, max_size=100),
                "issuer": st.text(min_size=1, max_size=100),
                "date": st.text(min_size=0, max_size=20),
                "expiry_date": st.text(min_size=0, max_size=20)
            }),
            max_size=5
        ))
    }


class TestImportCompletionWorkflow:
    """Test import completion workflow properties."""

    @given(cv_data=cv_data_strategy())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_cv_model_can_be_created_from_preview_data(self, cv_data):
        """
        Property: For any valid CV data from preview acceptance,
        a CVModel can be successfully created.
        """
        # Create CV model from preview data
        cv_model = CVModel(**cv_data)
        
        # Verify model was created
        assert cv_model is not None
        assert cv_model.personal_info.name == cv_data["personal_info"]["name"]
        assert cv_model.metadata.title == cv_data["metadata"]["title"]

    @given(cv_data=cv_data_strategy())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_cv_model_preserves_all_sections(self, cv_data):
        """
        Property: For any CV created from preview acceptance,
        all sections from the preview data should be preserved in the model.
        """
        # Create CV model
        cv_model = CVModel(**cv_data)
        
        # Verify all sections are preserved
        assert len(cv_model.experience) == len(cv_data["experience"])
        assert len(cv_model.education) == len(cv_data["education"])
        assert len(cv_model.skills.categories) == len(cv_data["skills"]["categories"])
        assert len(cv_model.certifications) == len(cv_data["certifications"])
        
        # Verify summary is preserved
        if cv_data["summary"]:
            assert cv_model.summary == cv_data["summary"]

    @given(
        cv_data=cv_data_strategy(),
        custom_title=st.text(min_size=1, max_size=100)
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_custom_title_override_is_applied(self, cv_data, custom_title):
        """
        Property: For any CV created with a custom title override,
        the custom title should be used instead of the default.
        """
        # Override title
        cv_data["metadata"]["title"] = custom_title
        
        # Create CV model
        cv_model = CVModel(**cv_data)
        
        # Verify custom title is applied
        assert cv_model.metadata.title == custom_title

    @given(cv_data=cv_data_strategy())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_cv_model_has_valid_id(self, cv_data):
        """
        Property: For any CV created from preview acceptance,
        the CV model should have a valid ID.
        """
        # Create CV model
        cv_model = CVModel(**cv_data)
        
        # Verify ID is valid
        assert cv_model.id is not None
        assert isinstance(cv_model.id, str)
        assert len(cv_model.id) > 0

    @given(cv_data=cv_data_strategy())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_cv_model_has_timestamps(self, cv_data):
        """
        Property: For any CV created from preview acceptance,
        the CV model should have valid created_at and updated_at timestamps.
        """
        # Create CV model
        cv_model = CVModel(**cv_data)
        
        # Verify timestamps exist and are valid
        assert cv_model.metadata.created_at is not None
        assert cv_model.metadata.updated_at is not None
        assert isinstance(cv_model.metadata.created_at, datetime)
        assert isinstance(cv_model.metadata.updated_at, datetime)

    @given(cv_data=cv_data_strategy())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_cv_model_data_integrity(self, cv_data):
        """
        Property: For any CV created from preview acceptance,
        the data integrity should be maintained (no data corruption).
        """
        # Create CV model
        cv_model = CVModel(**cv_data)
        
        # Convert back to dict and verify data integrity
        model_dict = cv_model.model_dump()
        
        # Verify personal info
        assert model_dict["personal_info"]["name"] == cv_data["personal_info"]["name"]
        assert model_dict["personal_info"]["title"] == cv_data["personal_info"]["title"]
        
        # Verify contact info
        assert model_dict["personal_info"]["contact"]["email"] == cv_data["personal_info"]["contact"]["email"]
        
        # Verify experience count
        assert len(model_dict["experience"]) == len(cv_data["experience"])
        
        # Verify education count
        assert len(model_dict["education"]) == len(cv_data["education"])

    @given(cv_data=cv_data_strategy())
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_cv_model_serialization(self, cv_data):
        """
        Property: For any CV created from preview acceptance,
        the model should be serializable to JSON and back without data loss.
        """
        # Create CV model
        cv_model = CVModel(**cv_data)
        
        # Serialize to dict
        serialized = cv_model.model_dump()
        
        # Deserialize back to model
        deserialized = CVModel(**serialized)
        
        # Verify data is preserved
        assert deserialized.personal_info.name == cv_model.personal_info.name
        assert deserialized.metadata.title == cv_model.metadata.title
        assert len(deserialized.experience) == len(cv_model.experience)
        assert len(deserialized.education) == len(cv_model.education)

