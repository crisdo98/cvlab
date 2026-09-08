# LLM Router Implementation

## Overview

The LLM router provides REST API endpoints for all AI-powered features in the CV Web Application. It integrates with multiple LLM providers (OpenAI, Anthropic, local models) and provides comprehensive CV enhancement capabilities.

## Implemented Endpoints

### Content Generation
- `POST /api/llm/generate-content` - Generate content for CV sections (summary, experience, education, skills)
- `POST /api/llm/expand-notes` - Expand brief notes into full professional descriptions
- `POST /api/llm/generate-achievements` - Generate quantifiable achievement statements

### CV Optimization
- `POST /api/llm/optimize-cv` - Comprehensive CV analysis with improvement recommendations
  - Weak language detection
  - Metrics gap identification
  - Structural analysis

### Job Tailoring
- `POST /api/llm/tailor-to-job` - Tailor CV to specific job descriptions
  - Job requirement extraction
  - Keyword matching
  - Content modification suggestions

### Grammar & Style
- `POST /api/llm/check-grammar` - Grammar and style checking
  - Grammar error detection
  - Passive voice detection
  - Tense consistency verification
  - Sentence complexity analysis

### ATS Analysis
- `POST /api/llm/analyze-ats` - ATS compatibility analysis
  - Compatibility scoring
  - Keyword optimization
  - Formatting checks

### AI Parsing
- `POST /api/llm/parse-cv` - Parse CVs from various formats (PDF, DOCX, TXT)
  - Section identification
  - Entity extraction
  - Ambiguity handling

### Configuration
- `GET /api/llm/config` - Get current LLM configuration
- `PUT /api/llm/config` - Update LLM configuration
- `POST /api/llm/test-connection` - Test LLM provider connection

## Features

### Multi-Provider Support
- OpenAI (GPT-3.5, GPT-4)
- Anthropic (Claude)
- Local models (Ollama, llama.cpp)

### Privacy & Security
- User consent management for external services
- API key encryption
- Local model option for complete privacy
- No data retention with external providers

### Error Handling
- Comprehensive error messages
- Graceful degradation
- Provider fallback support
- Rate limiting awareness

### Configuration Management
- Dynamic provider switching
- Per-feature configuration
- Global enable/disable toggle
- Secure API key storage

## Usage Example

```python
# Generate content
response = client.post("/api/llm/generate-content", json={
    "section_type": "summary",
    "context": {
        "job_title": "Senior Software Engineer",
        "years_experience": 5,
        "skills": ["Python", "FastAPI", "React"]
    },
    "num_variations": 3
})

# Optimize CV
response = client.post("/api/llm/optimize-cv", json={
    "cv_id": "uuid-here",
    "cv_data": {...},
    "include_reasoning": True
})

# Check grammar
response = client.post("/api/llm/check-grammar", json={
    "cv_id": "uuid-here",
    "cv_data": {...}
})
```

## Requirements Validated

This implementation validates the following requirements:
- 10.1-10.5: Content Generation
- 11.1-11.5: CV Optimization
- 12.1-12.5: Job Tailoring
- 13.1-13.5: Grammar & Style
- 14.1-14.5: ATS Analysis
- 15.1-15.5: AI Parsing
- 16.1-16.5: Configuration & Privacy

## Integration

The LLM router is registered in `backend/app/main.py` and is accessible at the `/api/llm` prefix. All endpoints require LLM to be configured and enabled, with user consent for external services.

## Next Steps

- Implement frontend components to consume these endpoints
- Add rate limiting middleware
- Implement configuration persistence
- Add LLM response caching
- Implement provider fallback logic
