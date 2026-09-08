"""
Property-Based Tests for CV Data Persistence

Tests Property 22: Complete state persistence round-trip
Validates: Requirements 9.5

Ensures that CV section configuration (sections, order, visibility) is
completely preserved through save and load operations.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from hypothesis import given, strategies as st, settings
from datetime import datetime

from app.models.cv_models import CVModelV2
from app.models.cv_section_models import (
    Section,
    SectionType,
    PersonalInfoContent,
    FreeTextSectionContent,
    ListSectionContent,
    StructuredSectionContent,
    ListItem,
    ExperienceEntry
)
from app.services.file_service import FileService


# Hypothesis strategies for generating test data

@st.composite
def personal_info_section_strategy(draw, order=0):
    """Generate a valid personal info section."""
    return Section(
        type=SectionType.PERSONAL_INFO,
        title=draw(st.text(min_size=1, max_size=50)),
        visible=draw(st.booleans()),
        order=order,
        content=PersonalInfoContent(
            full_name=draw(st.text(min_size=1, max_size=100)),
            email=draw(st.emails()),
            phone=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
            location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
            linkedin=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
            website=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
        )
    )


@st.composite
def summary_section_strategy(draw, order=1):
    """Generate a valid summary section."""
    return Section(
        type=SectionType.SUMMARY,
        title=draw(st.text(min_size=1, max_size=50)),
        visible=draw(st.booleans()),
        order=order,
        content=FreeTextSectionContent(
            text=draw(st.text(min_size=0, max_size=500))
        )
    )


@st.composite
def skills_section_strategy(draw, order=2):
    """Generate a valid skills section."""
    items = draw(st.lists(
        st.builds(ListItem, text=st.text(min_size=1, max_size=50)),
        min_size=0,
        max_size=10
    ))
    return Section(
        type=SectionType.SKILLS,
        title=draw(st.text(min_size=1, max_size=50)),
        visible=draw(st.booleans()),
        order=order,
        content=ListSectionContent(items=items)
    )


@st.composite
def experience_section_strategy(draw, order=3):
    """Generate a valid experience section."""
    entries = []
    for _ in range(draw(st.integers(min_value=0, max_value=3))):
        entry = ExperienceEntry(
            title=draw(st.text(min_size=1, max_size=100)),
            company=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
            location=draw(st.one_of(st.none(), st.text(min_size=1, max_size=100))),
            start_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
            end_date=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
            current=draw(st.booleans()),
            description=draw(st.one_of(st.none(), st.text(min_size=0, max_size=200))),
            achievements=draw(st.lists(st.text(min_size=1, max_size=100), max_size=3))
        )
        entries.append(entry)
    
    return Section(
        type=SectionType.EXPERIENCE,
        title=draw(st.text(min_size=1, max_size=50)),
        visible=draw(st.booleans()),
        order=order,
        content=StructuredSectionContent(entries=entries)
    )


@st.composite
def custom_section_strategy(draw, order=4):
    """Generate a valid custom section."""
    return Section(
        type=SectionType.CUSTOM,
        title=draw(st.text(min_size=1, max_size=50)),
        visible=draw(st.booleans()),
        order=order,
        content=FreeTextSectionContent(
            text=draw(st.text(min_size=0, max_size=500))
        )
    )


@st.composite
def cv_with_sections_strategy(draw):
    """Generate a complete CV with multiple sections."""
    sections = []
    order = 0
    
    # Always include personal info (core section)
    sections.append(draw(personal_info_section_strategy(order=order)))
    order += 1
    
    # Optionally add other sections
    if draw(st.booleans()):
        sections.append(draw(summary_section_strategy(order=order)))
        order += 1
    
    if draw(st.booleans()):
        sections.append(draw(skills_section_strategy(order=order)))
        order += 1
    
    if draw(st.booleans()):
        sections.append(draw(experience_section_strategy(order=order)))
        order += 1
    
    if draw(st.booleans()):
        sections.append(draw(custom_section_strategy(order=order)))
        order += 1
    
    return CVModelV2(
        user_id=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50))),
        sections=sections,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


class TestCompleteStatePersistenceProperty:
    """
    Property 22: Complete state persistence round-trip
    
    For any CV with specific sections, order, and visibility settings,
    saving and then loading the CV should restore the exact same configuration.
    
    Validates: Requirements 9.5
    """
    
    @given(cv=cv_with_sections_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_22_complete_state_persistence_round_trip(self, cv):
        """
        Feature: cv-section-management, Property 22: Complete state persistence round-trip
        
        Saving and loading a CV should preserve all section configuration:
        - All sections present
        - Section order preserved
        - Visibility settings preserved
        - Content preserved
        - Section IDs preserved
        """
        # Create temp directory for this test
        temp_dir = tempfile.mkdtemp()
        try:
            # Create file service with temp directory
            file_service = FileService(data_directory=temp_dir)
            
            # Save the CV
            file_service.save_cv(cv)
            
            # Load the CV back
            loaded_cv = file_service.load_cv(cv.id)
            
            # Verify it's a V2 model
            assert isinstance(loaded_cv, CVModelV2)
            assert loaded_cv.version == 2
            
            # Verify same number of sections
            assert len(loaded_cv.sections) == len(cv.sections)
            
            # Verify each section is preserved exactly
            for original_section, loaded_section in zip(cv.sections, loaded_cv.sections):
                # Section metadata preserved
                assert loaded_section.id == original_section.id
                assert loaded_section.type == original_section.type
                assert loaded_section.title == original_section.title
                assert loaded_section.visible == original_section.visible
                assert loaded_section.order == original_section.order
                
                # Content type preserved
                assert type(loaded_section.content) == type(original_section.content)
                
                # Content data preserved (check key fields based on type)
                if isinstance(original_section.content, PersonalInfoContent):
                    assert loaded_section.content.full_name == original_section.content.full_name
                    assert loaded_section.content.email == original_section.content.email
                    assert loaded_section.content.phone == original_section.content.phone
                    assert loaded_section.content.location == original_section.content.location
                
                elif isinstance(original_section.content, FreeTextSectionContent):
                    assert loaded_section.content.text == original_section.content.text
                
                elif isinstance(original_section.content, ListSectionContent):
                    assert len(loaded_section.content.items) == len(original_section.content.items)
                    for orig_item, loaded_item in zip(
                        original_section.content.items,
                        loaded_section.content.items
                    ):
                        assert loaded_item.text == orig_item.text
                
                elif isinstance(original_section.content, StructuredSectionContent):
                    assert len(loaded_section.content.entries) == len(original_section.content.entries)
                    for orig_entry, loaded_entry in zip(
                        original_section.content.entries,
                        loaded_section.content.entries
                    ):
                        # Check common fields
                        if hasattr(orig_entry, 'title'):
                            assert loaded_entry.title == orig_entry.title
                        if hasattr(orig_entry, 'company'):
                            assert loaded_entry.company == orig_entry.company
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir)
    
    @given(cv=cv_with_sections_strategy())
    @settings(max_examples=50, deadline=None)
    def test_property_22_section_order_preserved(self, cv):
        """
        Feature: cv-section-management, Property 22: Complete state persistence round-trip
        
        Section order must be preserved exactly through save/load cycle.
        """
        temp_dir = tempfile.mkdtemp()
        try:
            file_service = FileService(data_directory=temp_dir)
            
            # Save and load
            file_service.save_cv(cv)
            loaded_cv = file_service.load_cv(cv.id)
            
            # Extract order values
            original_orders = [s.order for s in cv.sections]
            loaded_orders = [s.order for s in loaded_cv.sections]
            
            # Order must be identical
            assert loaded_orders == original_orders
            
            # Sections must be in the same sequence
            for i, (orig, loaded) in enumerate(zip(cv.sections, loaded_cv.sections)):
                assert loaded.order == orig.order
                assert loaded.order == i  # Should be consecutive starting from 0
        finally:
            shutil.rmtree(temp_dir)
    
    @given(cv=cv_with_sections_strategy())
    @settings(max_examples=50, deadline=None)
    def test_property_22_visibility_settings_preserved(self, cv):
        """
        Feature: cv-section-management, Property 22: Complete state persistence round-trip
        
        Visibility settings for each section must be preserved.
        """
        temp_dir = tempfile.mkdtemp()
        try:
            file_service = FileService(data_directory=temp_dir)
            
            # Save and load
            file_service.save_cv(cv)
            loaded_cv = file_service.load_cv(cv.id)
            
            # Check visibility for each section
            for orig_section, loaded_section in zip(cv.sections, loaded_cv.sections):
                assert loaded_section.visible == orig_section.visible
            
            # Verify get_visible_sections returns same sections
            original_visible_ids = {s.id for s in cv.get_visible_sections()}
            loaded_visible_ids = {s.id for s in loaded_cv.get_visible_sections()}
            assert loaded_visible_ids == original_visible_ids
        finally:
            shutil.rmtree(temp_dir)
    
    @given(cv=cv_with_sections_strategy())
    @settings(max_examples=50, deadline=None)
    def test_property_22_section_ids_preserved(self, cv):
        """
        Feature: cv-section-management, Property 22: Complete state persistence round-trip
        
        Section IDs must remain stable across save/load operations.
        This is critical for frontend references and operations.
        """
        temp_dir = tempfile.mkdtemp()
        try:
            file_service = FileService(data_directory=temp_dir)
            
            # Collect original section IDs
            original_ids = [s.id for s in cv.sections]
            
            # Save and load
            file_service.save_cv(cv)
            loaded_cv = file_service.load_cv(cv.id)
            
            # Collect loaded section IDs
            loaded_ids = [s.id for s in loaded_cv.sections]
            
            # IDs must be identical and in same order
            assert loaded_ids == original_ids
            
            # Verify each section can be found by its original ID
            for orig_id in original_ids:
                found_section = loaded_cv.get_section_by_id(orig_id)
                assert found_section is not None
                assert found_section.id == orig_id
        finally:
            shutil.rmtree(temp_dir)
    
    @given(cv=cv_with_sections_strategy())
    @settings(max_examples=50, deadline=None)
    def test_property_22_multiple_save_load_cycles(self, cv):
        """
        Feature: cv-section-management, Property 22: Complete state persistence round-trip
        
        Multiple save/load cycles should not degrade data.
        """
        temp_dir = tempfile.mkdtemp()
        try:
            file_service = FileService(data_directory=temp_dir)
            
            # Perform multiple save/load cycles
            current_cv = cv
            for _ in range(3):
                file_service.save_cv(current_cv)
                current_cv = file_service.load_cv(current_cv.id)
            
            # After 3 cycles, data should still match original
            assert len(current_cv.sections) == len(cv.sections)
            
            for orig_section, final_section in zip(cv.sections, current_cv.sections):
                assert final_section.id == orig_section.id
                assert final_section.type == orig_section.type
                assert final_section.title == orig_section.title
                assert final_section.visible == orig_section.visible
                assert final_section.order == orig_section.order
        finally:
            shutil.rmtree(temp_dir)
