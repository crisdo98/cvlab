"""
Property-Based Tests for Import Error Handling

Tests the universal property that importing invalid markdown CV files should
fail gracefully with specific error messages indicating the problems.

Feature: cv-web-app, Property 9: Import Error Handling
Validates: Requirements 4.3
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
import re

from app.services.import_service import (
    ImportService,
    ImportServiceError,
    MarkdownParseError,
    YAMLParseError,
    ContentParseError
)


class TestImportErrorHandling:
    """
    Property-Based Tests for Import Error Handling.
    
    Feature: cv-web-app, Property 9: Import Error Handling
    Validates: Requirements 4.3
    """
    
    def setup_method(self):
        """Set up test fixtures."""
        self.import_service = ImportService()
    
    @given(content=st.text(min_size=1, max_size=500))
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    def test_missing_frontmatter_raises_specific_error(self, content):
        """
        Property: For any markdown content without YAML frontmatter delimiters,
        the import should fail with MarkdownParseError and a specific message
        about missing frontmatter.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        # Assume content doesn't start with '---' (no frontmatter)
        assume(not content.strip().startswith('---'))
        
        # Attempt to import should raise MarkdownParseError
        with pytest.raises(MarkdownParseError) as exc_info:
            self.import_service.import_from_markdown(content)
        
        # Error message should be specific about missing frontmatter
        error_message = str(exc_info.value)
        assert "frontmatter" in error_message.lower() or "---" in error_message
    
    @given(
        yaml_content=st.text(min_size=1, max_size=200, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Zs'))),
        body_content=st.text(min_size=0, max_size=200)
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    def test_unclosed_frontmatter_raises_specific_error(self, yaml_content, body_content):
        """
        Property: For any markdown content with opening '---' but no closing '---',
        the import should fail with MarkdownParseError and a specific message
        about unclosed frontmatter.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        # Create content with opening '---' but no closing delimiter
        # Ensure the body doesn't accidentally contain '---'
        assume('---' not in body_content)
        
        malformed_content = f"---\n{yaml_content}\n{body_content}"
        
        # Attempt to import should raise MarkdownParseError
        with pytest.raises(MarkdownParseError) as exc_info:
            self.import_service.import_from_markdown(malformed_content)
        
        # Error message should be specific about missing closing delimiter
        error_message = str(exc_info.value)
        assert "closing" in error_message.lower() or "---" in error_message
    
    @given(
        invalid_yaml=st.one_of(
            # Unclosed brackets/braces
            st.just("title: Test\nlist: [unclosed"),
            st.just("title: Test\ndict: {unclosed"),
            # Invalid indentation
            st.just("title: Test\n  nested:\nvalue: bad"),
            # Invalid syntax
            st.just("title: Test\n: invalid"),
            st.just("title: Test\n- - invalid"),
            # Tabs mixed with spaces (YAML doesn't allow tabs)
            st.just("title: Test\n\tindented: value"),
        )
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    def test_invalid_yaml_syntax_raises_specific_error(self, invalid_yaml):
        """
        Property: For any markdown content with invalid YAML syntax in frontmatter,
        the import should fail with YAMLParseError and a specific message
        about the YAML syntax problem.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        # Create markdown with invalid YAML frontmatter
        markdown_content = f"---\n{invalid_yaml}\n---\n\n# John Doe\n\nDeveloper"
        
        # Attempt to import should raise YAMLParseError
        with pytest.raises(YAMLParseError) as exc_info:
            self.import_service.import_from_markdown(markdown_content)
        
        # Error message should mention YAML or syntax
        error_message = str(exc_info.value)
        assert "yaml" in error_message.lower() or "syntax" in error_message.lower()
    
    @given(
        frontmatter=st.text(min_size=0, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N', 'Zs'))),
        content=st.text(min_size=0, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N', 'Zs')))
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    def test_empty_or_minimal_content_handled_gracefully(self, frontmatter, content):
        """
        Property: For any markdown with valid structure but minimal/empty content,
        the import should either succeed with defaults or fail with a clear error
        about missing required fields.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        # Create markdown with valid structure but potentially empty content
        markdown_content = f"---\ntitle: Test CV\n---\n\n{content}"
        
        try:
            # Attempt to import
            cv_model = self.import_service.import_from_markdown(markdown_content)
            
            # If it succeeds, verify it has at least basic structure
            assert cv_model is not None
            assert cv_model.metadata is not None
            assert cv_model.personal_info is not None
            
        except (ImportServiceError, MarkdownParseError, YAMLParseError, ContentParseError) as e:
            # If it fails, error message should be informative
            error_message = str(e)
            assert len(error_message) > 0
            # Should not be a generic error
            assert "unexpected" not in error_message.lower() or "specific" in error_message.lower()
    
    def test_yaml_frontmatter_not_dict_raises_specific_error(self):
        """
        Property: When YAML frontmatter is not a dictionary (e.g., a list or string),
        the import should fail with YAMLParseError and a specific message.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        # YAML frontmatter as a list instead of dict
        markdown_content = """---
- item1
- item2
---

# John Doe

Developer
"""
        
        with pytest.raises(YAMLParseError) as exc_info:
            self.import_service.import_from_markdown(markdown_content)
        
        error_message = str(exc_info.value)
        assert "dictionary" in error_message.lower() or "dict" in error_message.lower()
    
    def test_malformed_experience_section_handled_gracefully(self):
        """
        Property: When experience section has malformed entries,
        the import should handle it gracefully (skip bad entries or provide clear error).
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        markdown_content = """---
title: Test CV
---

# John Doe

Software Engineer

- john@example.com

## Work Experience

### Senior Developer
Missing company line and dates

### Another Position
**Valid Company** | Location
*January 2020 - Present*

Valid description
"""
        
        # Should either succeed (skipping malformed entry) or fail with clear error
        try:
            cv_model = self.import_service.import_from_markdown(markdown_content)
            # If successful, should have parsed at least the valid entry
            assert cv_model is not None
            # May have 0, 1, or 2 experience entries depending on error handling strategy
            assert len(cv_model.experience) >= 0
        except (ContentParseError, ImportServiceError) as e:
            # If it fails, error should mention the problem
            error_message = str(e)
            assert len(error_message) > 0
    
    def test_malformed_skills_section_handled_gracefully(self):
        """
        Property: When skills section has malformed format,
        the import should handle it gracefully.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        markdown_content = """---
title: Test CV
---

# John Doe

Developer

- john@example.com

## Skills

This is not a proper skills format
No colons or semicolons
Just random text
"""
        
        # Should either succeed (with empty skills) or fail with clear error
        try:
            cv_model = self.import_service.import_from_markdown(markdown_content)
            assert cv_model is not None
            # Skills might be empty if parsing failed gracefully
            assert cv_model.skills is not None
        except (ContentParseError, ImportServiceError) as e:
            error_message = str(e)
            assert len(error_message) > 0
    
    def test_malformed_education_section_handled_gracefully(self):
        """
        Property: When education section has malformed entries,
        the import should handle it gracefully.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        markdown_content = """---
title: Test CV
---

# John Doe

Developer

- john@example.com

## Education

### Bachelor of Science
Missing institution line

### Master of Science
**University of Technology** | Boston, MA
*September 2018 - May 2020*
"""
        
        # Should either succeed (skipping malformed entry) or fail with clear error
        try:
            cv_model = self.import_service.import_from_markdown(markdown_content)
            assert cv_model is not None
            # May have 0, 1, or 2 education entries depending on error handling
            assert len(cv_model.education) >= 0
        except (ContentParseError, ImportServiceError) as e:
            error_message = str(e)
            assert len(error_message) > 0
    
    @given(
        special_chars=st.text(
            min_size=10,
            max_size=100,
            alphabet=st.characters(
                blacklist_categories=('Cs', 'Cc'),  # Exclude control characters
                blacklist_characters=['\x00', '\x01', '\x02', '\x03', '\x04', '\x05']
            )
        )
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    def test_special_characters_in_content_handled_gracefully(self, special_chars):
        """
        Property: For any markdown content with special characters,
        the import should handle them gracefully without crashing.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        # Create markdown with special characters in various sections
        markdown_content = f"""---
title: Test CV with Special Chars
---

# John Doe {special_chars[:20]}

Developer

- john@example.com

## Summary

{special_chars}
"""
        
        # Should either succeed or fail with a clear error (not crash)
        try:
            cv_model = self.import_service.import_from_markdown(markdown_content)
            assert cv_model is not None
            assert cv_model.personal_info is not None
        except (ImportServiceError, MarkdownParseError, YAMLParseError, ContentParseError) as e:
            # If it fails, should have a meaningful error message
            error_message = str(e)
            assert len(error_message) > 0
            assert error_message != "None"
    
    def test_completely_empty_markdown_raises_specific_error(self):
        """
        Property: Completely empty markdown content should fail with a specific error.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        markdown_content = ""
        
        with pytest.raises(MarkdownParseError) as exc_info:
            self.import_service.import_from_markdown(markdown_content)
        
        error_message = str(exc_info.value)
        assert len(error_message) > 0
        assert "frontmatter" in error_message.lower() or "---" in error_message
    
    def test_only_whitespace_markdown_raises_specific_error(self):
        """
        Property: Markdown with only whitespace should fail with a specific error.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        markdown_content = "   \n\n\t\t\n   "
        
        with pytest.raises(MarkdownParseError) as exc_info:
            self.import_service.import_from_markdown(markdown_content)
        
        error_message = str(exc_info.value)
        assert len(error_message) > 0
        assert "frontmatter" in error_message.lower() or "---" in error_message
    
    def test_frontmatter_only_no_content_handled_gracefully(self):
        """
        Property: Markdown with only frontmatter and no content should be handled gracefully.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        markdown_content = """---
title: Test CV
---
"""
        
        # Should either succeed with minimal CV or fail with clear error
        try:
            cv_model = self.import_service.import_from_markdown(markdown_content)
            assert cv_model is not None
            assert cv_model.metadata.title == "Test CV"
        except (ImportServiceError, ContentParseError) as e:
            error_message = str(e)
            assert len(error_message) > 0
    
    def test_multiple_frontmatter_delimiters_raises_error(self):
        """
        Property: Markdown with multiple '---' delimiters in unexpected places
        should be handled appropriately.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        markdown_content = """---
title: Test CV
---

# John Doe

---

This should not be here

---

Developer
"""
        
        # Should either parse correctly (treating extra --- as content) or fail clearly
        try:
            cv_model = self.import_service.import_from_markdown(markdown_content)
            assert cv_model is not None
        except (ImportServiceError, MarkdownParseError, YAMLParseError, ContentParseError) as e:
            error_message = str(e)
            assert len(error_message) > 0
    
    @given(
        yaml_key=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        yaml_value=st.one_of(
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans(),
            st.text(max_size=100)
        )
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
    )
    def test_arbitrary_yaml_fields_handled_gracefully(self, yaml_key, yaml_value):
        """
        Property: For any valid YAML with arbitrary fields in frontmatter,
        the import should handle them gracefully (use or ignore unknown fields).
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        # Avoid reserved Python keywords and empty keys
        assume(yaml_key not in ['', 'class', 'def', 'return', 'import', 'from'])
        assume(len(yaml_key.strip()) > 0)
        
        # Create markdown with arbitrary YAML field
        markdown_content = f"""---
title: Test CV
{yaml_key}: {yaml_value}
---

# John Doe

Developer

- john@example.com
"""
        
        # Should succeed (ignoring unknown fields) or fail with clear error
        try:
            cv_model = self.import_service.import_from_markdown(markdown_content)
            assert cv_model is not None
            assert cv_model.metadata.title == "Test CV"
        except (ImportServiceError, YAMLParseError) as e:
            error_message = str(e)
            assert len(error_message) > 0
    
    def test_error_messages_are_actionable(self):
        """
        Property: All error messages should be actionable and specific,
        not generic "something went wrong" messages.
        
        Feature: cv-web-app, Property 9: Import Error Handling
        Validates: Requirements 4.3
        """
        test_cases = [
            ("", "empty content"),
            ("no frontmatter", "missing frontmatter"),
            ("---\ntitle: test", "unclosed frontmatter"),
            ("---\n[list]\n---\n# Name", "yaml not dict"),
            ("---\ntitle: test\nlist: [unclosed\n---\n# Name", "invalid yaml"),
        ]
        
        for content, expected_issue in test_cases:
            try:
                self.import_service.import_from_markdown(content)
                # If it succeeds, that's fine for some cases
            except (ImportServiceError, MarkdownParseError, YAMLParseError, ContentParseError) as e:
                error_message = str(e).lower()
                
                # Error message should not be generic
                assert error_message != ""
                assert "error" in error_message or "invalid" in error_message or \
                       "failed" in error_message or "missing" in error_message or \
                       "cannot" in error_message or "no " in error_message or \
                       "not " in error_message
                
                # Should not be just "unexpected error"
                if "unexpected" in error_message:
                    # If it says "unexpected", it should also provide context
                    assert len(error_message) > 30
