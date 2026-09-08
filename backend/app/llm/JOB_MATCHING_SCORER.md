# Job Matching Scorer

## Overview

The Job Matching Scorer provides comprehensive analysis of how well a CV matches a job description, similar to LinkedIn Premium's job matching feature. It calculates an overall match score (0-100%) with detailed breakdowns and actionable recommendations.

## Features

### 1. Overall Match Score (0-100%)
- Weighted combination of multiple scoring components
- Clear interpretation (excellent, good, moderate, low)
- Comparable across different job applications

### 2. Detailed Score Breakdown

The overall score is calculated from four components:

- **Keyword Alignment Score (25% weight)**: Measures how many job keywords are present in the CV
- **Skills Match Score (30% weight)**: Evaluates alignment between required skills and CV skills
- **Requirements Match Score (25% weight)**: Assesses how many job requirements are met
- **Experience Relevance Score (20% weight)**: Analyzes relevance of work experience to the role

### 3. Matched vs Missing Analysis

For each category, the scorer identifies:
- **Matched Skills**: Skills from the job description present in the CV
- **Missing Skills**: Required skills not found in the CV
- **Matched Requirements**: Job requirements the candidate meets
- **Missing Requirements**: Requirements not evidenced in the CV
- **Matched Keywords**: ATS keywords present in the CV
- **Missing Keywords**: Important keywords to incorporate

### 4. Qualification Gaps

Identifies significant gaps in qualifications:
- Critical missing skills
- Unmet requirements
- Experience level mismatches
- Educational qualification gaps

### 5. Candidate Strengths

Highlights positive aspects of the match:
- Strong skill alignment
- Relevant experience
- Met requirements
- Additional qualifications (certifications, education)

### 6. Actionable Recommendations

Provides specific suggestions to improve match score:
- Skills to highlight or develop
- Keywords to incorporate naturally
- Requirements to address
- CV tailoring strategies

## API Endpoint

### POST /api/llm/match-job

**Request:**
```json
{
  "cv_id": "uuid-string",
  "cv_data": {
    "personal_info": {...},
    "summary": "...",
    "experience": [...],
    "education": [...],
    "skills": {...},
    "certifications": [...]
  },
  "job_description": "Full job description text..."
}
```

**Response:**
```json
{
  "cv_id": "uuid-string",
  "job_analysis": {
    "job_title": "Senior Software Engineer",
    "company": "TechCorp Inc",
    "requirements": [...],
    "skills": [...],
    "keywords": [...],
    "experience_level": "Senior level",
    "industry": "Technology"
  },
  "score_breakdown": {
    "overall_score": 72.5,
    "keyword_alignment_score": 68.0,
    "experience_relevance_score": 75.0,
    "skills_match_score": 80.0,
    "requirements_match_score": 65.0
  },
  "matched_skills": ["Python", "JavaScript", "AWS", "Docker"],
  "missing_skills": ["Kubernetes", "Go"],
  "matched_requirements": [
    "5+ years of software development experience",
    "Strong knowledge of Python and JavaScript"
  ],
  "missing_requirements": [
    "Leadership and mentoring experience",
    "Bachelor's degree in Computer Science"
  ],
  "matched_keywords": ["Software Development", "Cloud Computing", "CI/CD"],
  "missing_keywords": ["Microservices", "GraphQL"],
  "qualification_gaps": [
    "Missing key skills: Kubernetes, Go",
    "Requirement not met: Bachelor's degree in Computer Science"
  ],
  "strengths": [
    "Strong skill alignment with 4 matching skills",
    "Meets 2 key job requirements",
    "Direct experience as Software Engineer"
  ],
  "recommendations": [
    "Highlight or develop these skills: Kubernetes, Go",
    "Incorporate these keywords naturally: Microservices, GraphQL",
    "Address 2 unmet requirements in your CV or cover letter"
  ],
  "summary": "Your CV shows a good match (72.5/100) for the Senior Software Engineer position. Your skills align well (80%). You match 4 of the required skills and are missing 2 skills. There are 2 qualification gaps to address. You are a competitive candidate with some areas for improvement.",
  "analyzed_at": "2024-01-15T10:30:00Z",
  "model": "gpt-4",
  "provider": "openai"
}
```

## Implementation Details

### Core Method: `match_cv_to_job()`

Located in `backend/app/llm/cv_optimizer.py`, this async method:

1. **Analyzes the job description** using LLM to extract:
   - Job title, company, industry
   - Requirements and qualifications
   - Required skills
   - Important keywords
   - Experience level

2. **Extracts CV data**:
   - All skills from skills section
   - Keywords from experience descriptions
   - Work experience details

3. **Performs matching**:
   - Keyword matching (fuzzy matching for variations)
   - Skills matching (case-insensitive with partial matches)
   - Requirements matching (uses LLM for nuanced analysis)
   - Experience relevance calculation

4. **Calculates scores**:
   - Individual component scores (0-100)
   - Weighted overall score
   - Score breakdown for transparency

5. **Generates insights**:
   - Identifies qualification gaps
   - Highlights candidate strengths
   - Creates actionable recommendations
   - Generates comprehensive summary

### Scoring Algorithm

#### Keyword Alignment Score
```
score = (matched_keywords / total_keywords) * 100
```

#### Skills Match Score
```
score = (matched_skills / total_skills) * 100
```

#### Requirements Match Score
```
score = (matched_requirements / total_requirements) * 100
```

#### Experience Relevance Score
Calculated based on:
- Job title match: 40 points
- Industry/field match: 30 points
- Experience level match: 30 points

#### Overall Score
```
overall = (
    keyword_score * 0.25 +
    skills_score * 0.30 +
    requirements_score * 0.25 +
    experience_score * 0.20
)
```

### LLM Integration

The scorer uses LLM for:
1. **Job description analysis**: Extracting structured information
2. **Requirements matching**: Nuanced evaluation of whether requirements are met
3. **Fallback**: If LLM fails, uses rule-based keyword matching

### Error Handling

- Validates job description length (minimum 10 characters)
- Handles LLM failures with graceful fallback
- Returns neutral scores (50.0) when data is insufficient
- Provides detailed error messages

## Usage Example

```python
from app.llm.cv_optimizer import CVOptimizer
from app.llm.providers import ProviderFactory, LLMConfig
from app.models.llm_models import JobMatchRequest

# Create LLM provider
config = LLMConfig(
    provider="openai",
    model="gpt-4",
    api_key="your-api-key"
)
provider = ProviderFactory.create_provider(config)

# Create optimizer
optimizer = CVOptimizer(provider)

# Prepare request
request = JobMatchRequest(
    cv_id="cv-uuid",
    cv_data={...},  # Full CV data
    job_description="Full job description text..."
)

# Get match analysis
result = await optimizer.match_cv_to_job(request)

# Use results
print(f"Overall Match: {result.score_breakdown.overall_score:.1f}%")
print(f"Matched Skills: {', '.join(result.matched_skills)}")
print(f"Missing Skills: {', '.join(result.missing_skills)}")
print(f"\nRecommendations:")
for rec in result.recommendations:
    print(f"- {rec}")
```

## Testing

Comprehensive test suite in `backend/tests/test_job_matching_scorer_basic.py`:

- Basic job matching functionality
- Skill matching accuracy
- Requirement matching
- Qualification gap identification
- Strength identification
- Recommendation generation
- Score calculation algorithms
- Edge cases (empty CV, minimal data)
- Summary quality

Run tests:
```bash
python -m pytest backend/tests/test_job_matching_scorer_basic.py -v
```

## Performance Considerations

- **LLM Calls**: Makes 2 LLM calls per match (job analysis + requirement matching)
- **Caching**: Consider caching job analysis for repeated matches
- **Timeout**: Uses configurable timeout for LLM calls
- **Fallback**: Rule-based matching if LLM unavailable

## Privacy and Security

- **Data Minimization**: Only sends necessary CV summary to LLM
- **Consent**: Requires user consent for external LLM services
- **Local Option**: Works with local LLM providers for complete privacy
- **No Storage**: Does not store job descriptions or match results with external providers

## Future Enhancements

1. **Machine Learning**: Train ML model on match outcomes for improved accuracy
2. **Industry-Specific**: Customize scoring weights by industry
3. **Historical Analysis**: Track match scores over time
4. **Batch Matching**: Match one CV against multiple jobs efficiently
5. **Confidence Scores**: Add confidence levels to each component
6. **Explainability**: Provide more detailed explanations for scores

## Related Features

- **Job Tailoring** (`tailor_cv_to_job`): Uses match analysis to suggest CV modifications
- **CV Optimization** (`optimize_cv`): General CV improvement recommendations
- **ATS Analysis** (`analyze_ats`): ATS compatibility scoring
- **Job URL Parsing** (`parse_job_url`): Extract job descriptions from URLs

## Requirements Validation

This implementation satisfies:
- **Requirement 12.4**: Job matching analysis with compatibility percentage (0-100%)
- **Requirement 12.5**: Detailed breakdown including matched skills, missing requirements, keyword alignment, experience relevance, and qualification gaps

## References

- Design Document: `.kiro/specs/cv-web-app/design.md`
- Requirements: `.kiro/specs/cv-web-app/requirements.md`
- Tasks: `.kiro/specs/cv-web-app/tasks.md` (Task 19.3)
- Models: `backend/app/models/llm_models.py`
- Implementation: `backend/app/llm/cv_optimizer.py`
- API Router: `backend/app/routers/llm_router.py`
- Tests: `backend/tests/test_job_matching_scorer_basic.py`
