"""
Tests for Import Service

Tests the markdown import functionality including YAML frontmatter parsing,
content section parsing, and conversion to CV models.
"""

import pytest
from datetime import datetime

from app.services.import_service import (
    ImportService,
    ImportServiceError,
    MarkdownParseError,
    YAMLParseError,
    ContentParseError
)
from app.models.cv_models import CVModel


class TestImportService:
    """Test the ImportService functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.import_service = ImportService()
    
    def test_import_basic_markdown_cv(self):
        """Test importing a basic markdown CV with all sections."""
        markdown_content = """---
title: Test CV
author: John Doe
subject: Resume
keywords: [software, engineering, python]
---

# John Doe

Senior Software Engineer

- 123 Main St, City, State 12345
- +1-555-123-4567
- john.doe@example.com
- LinkedIn: https://linkedin.com/in/johndoe

## Summary

Experienced software engineer with expertise in Python and web development.

## Work Experience

### Senior Software Engineer — Tech Corp (San Francisco, CA)
January 2020 — Current

Lead development of web applications using Python and JavaScript.

- Improved system performance by 50%
- Led team of 5 developers
- Implemented CI/CD pipeline

### Software Engineer — StartupCo (New York, NY)
June 2018 — December 2019

Developed backend services and APIs.

- Built REST APIs using Flask
- Worked with PostgreSQL databases

## Skills

- Programming Languages: Python; JavaScript; TypeScript; Java
- Frameworks: Django; Flask; React; Vue.js

## Education

- September 2014 — May 2018 — University of Technology (Boston, MA)
- Bachelor of Science in Computer Science
- GPA: 3.8

## Professional Memberships and Certificates

- June 2023 — AWS Certified Solutions Architect
- January 2022 — Certified Kubernetes Administrator (CNCF)
"""
        
        # Import the CV
        cv_model = self.import_service.import_from_markdown(markdown_content)
        
        # Verify the CV model
        assert isinstance(cv_model, CVModel)
        assert cv_model.metadata.title == "Test CV"
        assert cv_model.personal_info.name == "John Doe"
        assert cv_model.personal_info.title == "Senior Software Engineer"
        assert cv_model.personal_info.contact.email == "john.doe@example.com"
        assert cv_model.personal_info.contact.phone == "+1-555-123-4567"
        assert cv_model.personal_info.contact.linkedin == "https://linkedin.com/in/johndoe"
        
        # Verify summary
        assert "Experienced software engineer" in cv_model.summary
        
        # Verify experience
        assert len(cv_model.experience) == 2
        first_exp = cv_model.experience[0]
        assert first_exp.title == "Senior Software Engineer"
        assert first_exp.company == "Tech Corp"
        assert first_exp.location == "San Francisco, CA"
        assert first_exp.start_date == "January 2020"
        assert first_exp.current == True
        assert len(first_exp.achievements) == 3
        
        # Verify skills
        assert len(cv_model.skills.categories) == 2
        prog_langs = next((cat for cat in cv_model.skills.categories if cat.name == "Programming Languages"), None)
        assert prog_langs is not None
        assert "Python" in prog_langs.skills
        assert "JavaScript" in prog_langs.skills
        
        # Verify education
        assert len(cv_model.education) == 1
        education = cv_model.education[0]
        assert education.degree == "Bachelor of Science in Computer Science"
        assert education.institution == "University of Technology"
        assert education.location == "Boston, MA"
        
        # Verify certifications
        assert len(cv_model.certifications) == 2
        aws_cert = next((cert for cert in cv_model.certifications if "AWS" in cert.name), None)
        assert aws_cert is not None
        assert aws_cert.date == "June 2023"
    
    def test_import_minimal_markdown_cv(self):
        """Test importing a minimal markdown CV with only required fields."""
        markdown_content = """---
title: Minimal CV
---

# Jane Smith

Developer

- jane@example.com

## Summary

A brief summary.
"""
        
        cv_model = self.import_service.import_from_markdown(markdown_content)
        
        assert cv_model.metadata.title == "Minimal CV"
        assert cv_model.personal_info.name == "Jane Smith"
        assert cv_model.personal_info.title == "Developer"
        assert cv_model.personal_info.contact.email == "jane@example.com"
        assert cv_model.summary == "A brief summary."
        assert len(cv_model.experience) == 0
        assert len(cv_model.education) == 0
        assert len(cv_model.skills.categories) == 0
        assert len(cv_model.certifications) == 0
    
    def test_import_with_title_override(self):
        """Test importing with title override."""
        markdown_content = """---
title: Original Title
---

# John Doe

Developer
"""
        
        cv_model = self.import_service.import_from_markdown(markdown_content, "Override Title")
        
        assert cv_model.metadata.title == "Override Title"
        assert cv_model.personal_info.name == "John Doe"
    
    def test_import_invalid_yaml_frontmatter(self):
        """Test importing with invalid YAML frontmatter."""
        markdown_content = """---
title: Test CV
invalid_yaml: [unclosed list
---

# John Doe
"""
        
        with pytest.raises(YAMLParseError):
            self.import_service.import_from_markdown(markdown_content)
    
    def test_import_missing_frontmatter(self):
        """Test importing without YAML frontmatter."""
        markdown_content = """# John Doe

Developer
"""
        
        with pytest.raises(MarkdownParseError):
            self.import_service.import_from_markdown(markdown_content)
    
    def test_import_malformed_frontmatter(self):
        """Test importing with malformed frontmatter structure."""
        markdown_content = """---
title: Test CV

# John Doe

Developer
"""
        
        with pytest.raises(MarkdownParseError):
            self.import_service.import_from_markdown(markdown_content)
    
    def test_split_frontmatter_success(self):
        """Test successful frontmatter splitting."""
        markdown_content = """---
title: Test
---

# Content"""
        
        frontmatter, content = self.import_service._split_frontmatter(markdown_content)
        
        assert frontmatter.strip() == "title: Test"
        assert content.strip() == "# Content"
    
    def test_parse_yaml_frontmatter_success(self):
        """Test successful YAML parsing."""
        yaml_content = """title: Test CV
author: John Doe
keywords: [python, web]"""
        
        result = self.import_service._parse_yaml_frontmatter(yaml_content)
        
        assert result["title"] == "Test CV"
        assert result["author"] == "John Doe"
        assert result["keywords"] == ["python", "web"]
    
    def test_parse_personal_info_with_contact_details(self):
        """Test parsing personal info with various contact formats."""
        name_line = "John Doe"
        contact_content = """Software Engineer

- 123 Main St, City, State 12345
- +1-555-123-4567
- john.doe@example.com
- LinkedIn: https://linkedin.com/in/johndoe
- https://johndoe.dev"""
        
        result = self.import_service._parse_personal_info(name_line, contact_content)
        
        assert result["name"] == "John Doe"
        assert result["title"] == "Software Engineer"
        assert result["contact"]["address"] == "123 Main St, City, State 12345"
        assert result["contact"]["phone"] == "+1-555-123-4567"
        assert result["contact"]["email"] == "john.doe@example.com"
        assert result["contact"]["linkedin"] == "https://linkedin.com/in/johndoe"
        assert result["contact"]["website"] == "https://johndoe.dev"
    
    def test_parse_experience_section(self):
        """Test parsing work experience section."""
        content = """### Senior Developer — TechCorp (San Francisco, CA)
January 2020 — Current

Lead development of web applications.

- Improved performance by 50%
- Led team of 5 developers

### Junior Developer — StartupCo (New York, NY)
June 2018 — December 2019

Developed backend services."""
        
        result = self.import_service._parse_experience_section(content)
        
        assert len(result) == 2
        
        first_exp = result[0]
        assert first_exp["title"] == "Senior Developer"
        assert first_exp["company"] == "TechCorp"
        assert first_exp["location"] == "San Francisco, CA"
        assert first_exp["start_date"] == "January 2020"
        assert first_exp["current"] == True
        assert len(first_exp["achievements"]) == 2
        
        second_exp = result[1]
        assert second_exp["title"] == "Junior Developer"
        assert second_exp["company"] == "StartupCo"
        assert second_exp["current"] == False
    
    def test_parse_skills_section(self):
        """Test parsing skills section."""
        content = """- Programming Languages: Python; JavaScript; TypeScript
- Frameworks: Django; Flask; React
- Databases: PostgreSQL; MongoDB"""
        
        result = self.import_service._parse_skills_section(content)
        
        assert len(result["categories"]) == 3
        
        prog_langs = next((cat for cat in result["categories"] if cat["name"] == "Programming Languages"), None)
        assert prog_langs is not None
        assert "Python" in prog_langs["skills"]
        assert "JavaScript" in prog_langs["skills"]
        assert "TypeScript" in prog_langs["skills"]
    
    def test_parse_education_section(self):
        """Test parsing education section."""
        content = """- September 2014 — May 2018 — University of Technology (Boston, MA)
- Bachelor of Science in Computer Science
- GPA: 3.8
- Relevant coursework in algorithms and data structures"""
        
        result = self.import_service._parse_education_section(content)
        
        assert len(result) == 1
        education = result[0]
        assert education["start_date"] == "September 2014"
        assert education["end_date"] == "May 2018"
        assert education["institution"] == "University of Technology"
        assert education["location"] == "Boston, MA"
        assert education["degree"] == "Bachelor of Science in Computer Science"
    
    def test_parse_certifications_section(self):
        """Test parsing certifications section."""
        content = """- June 2023 — AWS Certified Solutions Architect
- January 2022 — Certified Kubernetes Administrator (CNCF)"""
        
        result = self.import_service._parse_certifications_section(content)
        
        assert len(result) == 2
        
        aws_cert = result[0]
        assert aws_cert["name"] == "AWS Certified Solutions Architect"
        assert aws_cert["date"] == "June 2023"
        
        k8s_cert = result[1]
        assert k8s_cert["name"] == "Certified Kubernetes Administrator"
        assert k8s_cert["issuer"] == "CNCF"
        assert k8s_cert["date"] == "January 2022"