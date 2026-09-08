"""
Property-Based Tests for Search and Filter Operations

Tests Properties 12-16: Search and filter correctness properties
Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5

Ensures that search and filter operations maintain correct behavior for:
- Search query matching (company name and position title)
- Stage filter correctness
- Date range filter correctness
- Multiple filter composition (AND logic)
- Filter clear returns all applications
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import datetime, timedelta
import tempfile
import shutil
from contextlib import contextmanager

from app.models.application_tracker_models import (
    Application,
    CreateApplicationRequest,
    ApplicationFilters,
    Interview,
    Stage
)
from app.services.application_tracker_service import ApplicationTrackerService
from app.services.application_tracker_storage import ApplicationTrackerStorage


@contextmanager
def temp_service():
    """Context manager for temporary service with isolated storage."""
    temp_dir = tempfile.mkdtemp()
    storage = ApplicationTrackerStorage(data_directory=temp_dir)
    service = ApplicationTrackerService(storage=storage, cv_service=None)
    try:
        yield service
    finally:
        shutil.rmtree(temp_dir)


# Hypothesis strategies for generating test data

@st.composite
def valid_email_strategy(draw):
    """Generate valid email addresses."""
    username = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'), 
        whitelist_characters='._-'
    )))
    domain = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-'
    )))
    tld = draw(st.sampled_from(['com', 'org', 'net', 'edu', 'io']))
    return f"{username}@{domain}.{tld}"


@st.composite
def valid_url_strategy(draw):
    """Generate valid HTTP/HTTPS URLs."""
    protocol = draw(st.sampled_from(['http', 'https']))
    domain = draw(st.text(min_size=1, max_size=30, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-'
    )))
    tld = draw(st.sampled_from(['com', 'org', 'net', 'io', 'co']))
    path = draw(st.one_of(
        st.none(),
        st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters='/-_'
        ))
    ))
    
    url = f"{protocol}://{domain}.{tld}"
    if path:
        url += f"/{path}"
    return url


@st.composite
def valid_interview_strategy(draw):
    """Generate valid Interview instances."""
    interview_date = draw(st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31)
    ))
    interview_type = draw(st.sampled_from(['phone', 'video', 'onsite', 'technical', 'behavioral']))
    meeting_link = draw(st.one_of(st.none(), valid_url_strategy()))
    notes = draw(st.one_of(st.none(), st.text(min_size=0, max_size=500)))
    interviewer_name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    
    return Interview(
        date=interview_date,
        type=interview_type,
        meeting_link=meeting_link,
        notes=notes,
        interviewer_name=interviewer_name
    )


@st.composite
def valid_application_request_strategy(draw):
    """Generate valid CreateApplicationRequest instances."""
    company_name = draw(st.text(min_size=1, max_size=200))
    position_title = draw(st.text(min_size=1, max_size=200))
    stage = draw(st.sampled_from(Stage))
    application_date = draw(st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31)
    ))
    
    job_description_url = draw(st.one_of(st.none(), valid_url_strategy()))
    application_deadline = draw(st.one_of(
        st.none(),
        st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    ))
    
    recruiter_name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    recruiter_email = draw(st.one_of(st.none(), valid_email_strategy()))
    recruiter_phone = draw(st.one_of(st.none(), st.text(min_size=5, max_size=20)))
    hiring_manager_name = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    
    interviews = draw(st.lists(valid_interview_strategy(), min_size=0, max_size=5))
    
    notes = draw(st.one_of(st.none(), st.text(min_size=0, max_size=1000)))
    tasks = draw(st.lists(st.text(min_size=1, max_size=200), min_size=0, max_size=10))
    
    feedback = draw(st.one_of(st.none(), st.text(min_size=0, max_size=1000)))
    outcome = draw(st.one_of(st.none(), st.text(min_size=0, max_size=500)))
    
    cv_version_id = draw(st.one_of(st.none(), st.text(min_size=1, max_size=100)))
    
    follow_up_date = draw(st.one_of(
        st.none(),
        st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    ))
    
    return CreateApplicationRequest(
        company_name=company_name,
        position_title=position_title,
        stage=stage,
        application_date=application_date,
        job_description_url=job_description_url,
        application_deadline=application_deadline,
        recruiter_name=recruiter_name,
        recruiter_email=recruiter_email,
        recruiter_phone=recruiter_phone,
        hiring_manager_name=hiring_manager_name,
        interviews=interviews,
        notes=notes,
        tasks=tasks,
        feedback=feedback,
        outcome=outcome,
        cv_version_id=cv_version_id,
        follow_up_date=follow_up_date
    )


class TestSearchQueryMatchingProperty:
    """
    Property 12: Search Query Matching
    
    For any search query string and any set of applications, the search results
    should only include applications where the company name or position title
    contains the query string (case-insensitive), and should include all such
    matching applications.
    
    Validates: Requirement 7.1
    """
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=20),
        search_query=st.text(min_size=1, max_size=50)
    )
    @settings(max_examples=50, deadline=None)
    def test_property_12_search_matches_company_or_position(self, requests, search_query):
        """
        Feature: job-application-tracker, Property 12: Search Query Matching
        
        Search results should only include applications matching the query in
        company name or position title (case-insensitive).
        
        Validates: Requirement 7.1 - Search query matching
        """
        # Ensure we have at least 5 applications
        assume(len(requests) >= 5)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Apply search filter
            filters = ApplicationFilters(search=search_query)
            results = service.list_applications(filters)
            
            # Verify all results match the search query
            search_lower = search_query.lower()
            for app in results:
                matches = (
                    search_lower in app.company_name.lower() or
                    search_lower in app.position_title.lower()
                )
                assert matches, \
                    f"Application {app.id} in results but doesn't match query '{search_query}': " \
                    f"company='{app.company_name}', position='{app.position_title}'"
            
            # Verify all matching applications are included
            expected_matches = [
                app for app in created_apps
                if search_lower in app.company_name.lower() or
                   search_lower in app.position_title.lower()
            ]
            
            result_ids = {app.id for app in results}
            expected_ids = {app.id for app in expected_matches}
            
            assert result_ids == expected_ids, \
                f"Search results incomplete: expected {len(expected_ids)} matches, got {len(result_ids)}"
    
    @given(requests=st.lists(valid_application_request_strategy(), min_size=3, max_size=15))
    @settings(max_examples=20, deadline=None)
    def test_property_12_search_case_insensitive(self, requests):
        """
        Feature: job-application-tracker, Property 12: Search Query Matching
        
        Search should be case-insensitive.
        
        Validates: Requirement 7.1 - Case-insensitive search
        """
        # Ensure we have at least 3 applications
        assume(len(requests) >= 3)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Pick an application and search with different cases
            if created_apps:
                target_app = created_apps[0]
                # Extract a substring from company name
                if len(target_app.company_name) >= 3:
                    substring = target_app.company_name[:3]
                    
                    # Search with lowercase
                    filters_lower = ApplicationFilters(search=substring.lower())
                    results_lower = service.list_applications(filters_lower)
                    
                    # Search with uppercase
                    filters_upper = ApplicationFilters(search=substring.upper())
                    results_upper = service.list_applications(filters_upper)
                    
                    # Results should be the same
                    result_ids_lower = {app.id for app in results_lower}
                    result_ids_upper = {app.id for app in results_upper}
                    
                    assert result_ids_lower == result_ids_upper, \
                        "Case-insensitive search failed: different results for different cases"
    
    @given(requests=st.lists(valid_application_request_strategy(), min_size=1, max_size=10))
    @settings(max_examples=20, deadline=None)
    def test_property_12_empty_search_returns_all(self, requests):
        """
        Feature: job-application-tracker, Property 12: Search Query Matching
        
        Empty or None search should return all applications.
        
        Validates: Requirement 7.1 - Empty search behavior
        """
        # Ensure we have at least 1 application
        assume(len(requests) >= 1)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Search with None
            filters_none = ApplicationFilters(search=None)
            results_none = service.list_applications(filters_none)
            
            # Search with empty string
            filters_empty = ApplicationFilters(search="")
            results_empty = service.list_applications(filters_empty)
            
            # Both should return all applications
            assert len(results_none) == len(created_apps), \
                f"None search should return all {len(created_apps)} applications, got {len(results_none)}"
            assert len(results_empty) == len(created_apps), \
                f"Empty search should return all {len(created_apps)} applications, got {len(results_empty)}"


class TestStageFilterCorrectnessProperty:
    """
    Property 13: Stage Filter Correctness
    
    For any stage filter value and any set of applications, the filtered results
    should only include applications in the specified stage, and should include
    all applications in that stage.
    
    Validates: Requirement 7.2
    """
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=20),
        filter_stage=st.sampled_from(Stage)
    )
    @settings(max_examples=20, deadline=None)
    def test_property_13_stage_filter_only_includes_matching(self, requests, filter_stage):
        """
        Feature: job-application-tracker, Property 13: Stage Filter Correctness
        
        Stage filter should only include applications in the specified stage.
        
        Validates: Requirement 7.2 - Stage filter correctness
        """
        # Ensure we have at least 5 applications
        assume(len(requests) >= 5)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Apply stage filter
            filters = ApplicationFilters(stage=filter_stage)
            results = service.list_applications(filters)
            
            # Verify all results have the filtered stage
            for app in results:
                assert app.stage == filter_stage, \
                    f"Application {app.id} in results but has stage {app.stage}, expected {filter_stage}"
            
            # Verify all applications with the stage are included
            expected_matches = [app for app in created_apps if app.stage == filter_stage]
            
            result_ids = {app.id for app in results}
            expected_ids = {app.id for app in expected_matches}
            
            assert result_ids == expected_ids, \
                f"Stage filter incomplete: expected {len(expected_ids)} matches, got {len(result_ids)}"
    
    @given(requests=st.lists(valid_application_request_strategy(), min_size=1, max_size=10))
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.data_too_large])
    def test_property_13_no_stage_filter_returns_all(self, requests):
        """
        Feature: job-application-tracker, Property 13: Stage Filter Correctness
        
        No stage filter (None) should return all applications.
        
        Validates: Requirement 7.2 - No filter behavior
        """
        # Ensure we have at least 1 application
        assume(len(requests) >= 1)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Apply no stage filter
            filters = ApplicationFilters(stage=None)
            results = service.list_applications(filters)
            
            # Should return all applications
            assert len(results) == len(created_apps), \
                f"No stage filter should return all {len(created_apps)} applications, got {len(results)}"
    
    @given(requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=15))
    @settings(max_examples=20, deadline=None)
    def test_property_13_each_stage_filter_works(self, requests):
        """
        Feature: job-application-tracker, Property 13: Stage Filter Correctness
        
        Each stage filter should work correctly.
        
        Validates: Requirement 7.2 - All stage filters
        """
        # Ensure we have at least 10 applications
        assume(len(requests) >= 10)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Test each stage filter
            for stage in Stage:
                filters = ApplicationFilters(stage=stage)
                results = service.list_applications(filters)
                
                # Count expected matches
                expected_count = sum(1 for app in created_apps if app.stage == stage)
                
                # Verify count matches
                assert len(results) == expected_count, \
                    f"Stage filter {stage} returned {len(results)} applications, expected {expected_count}"
                
                # Verify all have correct stage
                for app in results:
                    assert app.stage == stage, \
                        f"Application {app.id} has stage {app.stage}, expected {stage}"


class TestDateRangeFilterCorrectnessProperty:
    """
    Property 14: Date Range Filter Correctness
    
    For any date range (start and end dates) and any set of applications, the
    filtered results should only include applications with application_date within
    the range (inclusive), and should include all such applications.
    
    Validates: Requirement 7.3
    """
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=20),
        date_from=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 12, 31)),
        date_to=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 12, 31))
    )
    @settings(max_examples=20, deadline=None)
    def test_property_14_date_range_filter_inclusive(self, requests, date_from, date_to):
        """
        Feature: job-application-tracker, Property 14: Date Range Filter Correctness
        
        Date range filter should include applications within the range (inclusive).
        
        Validates: Requirement 7.3 - Date range filter correctness
        """
        # Ensure we have at least 5 applications and valid date range
        assume(len(requests) >= 5)
        assume(date_from <= date_to)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Apply date range filter
            filters = ApplicationFilters(date_from=date_from, date_to=date_to)
            results = service.list_applications(filters)
            
            # Verify all results are within the date range
            for app in results:
                assert date_from <= app.application_date <= date_to, \
                    f"Application {app.id} date {app.application_date} outside range " \
                    f"[{date_from}, {date_to}]"
            
            # Verify all applications within range are included
            expected_matches = [
                app for app in created_apps
                if date_from <= app.application_date <= date_to
            ]
            
            result_ids = {app.id for app in results}
            expected_ids = {app.id for app in expected_matches}
            
            assert result_ids == expected_ids, \
                f"Date range filter incomplete: expected {len(expected_ids)} matches, got {len(result_ids)}"
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=20),
        date_from=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    )
    @settings(max_examples=20, deadline=None)
    def test_property_14_date_from_filter_only(self, requests, date_from):
        """
        Feature: job-application-tracker, Property 14: Date Range Filter Correctness
        
        Date from filter (without date to) should include all applications on or after date_from.
        
        Validates: Requirement 7.3 - Date from filter
        """
        # Ensure we have at least 5 applications
        assume(len(requests) >= 5)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Apply date from filter only
            filters = ApplicationFilters(date_from=date_from, date_to=None)
            results = service.list_applications(filters)
            
            # Verify all results are on or after date_from
            for app in results:
                assert app.application_date >= date_from, \
                    f"Application {app.id} date {app.application_date} before {date_from}"
            
            # Verify all applications on or after date_from are included
            expected_matches = [app for app in created_apps if app.application_date >= date_from]
            
            result_ids = {app.id for app in results}
            expected_ids = {app.id for app in expected_matches}
            
            assert result_ids == expected_ids, \
                f"Date from filter incomplete: expected {len(expected_ids)} matches, got {len(result_ids)}"
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=20),
        date_to=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))
    )
    @settings(max_examples=20, deadline=None)
    def test_property_14_date_to_filter_only(self, requests, date_to):
        """
        Feature: job-application-tracker, Property 14: Date Range Filter Correctness
        
        Date to filter (without date from) should include all applications on or before date_to.
        
        Validates: Requirement 7.3 - Date to filter
        """
        # Ensure we have at least 5 applications
        assume(len(requests) >= 5)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Apply date to filter only
            filters = ApplicationFilters(date_from=None, date_to=date_to)
            results = service.list_applications(filters)
            
            # Verify all results are on or before date_to
            for app in results:
                assert app.application_date <= date_to, \
                    f"Application {app.id} date {app.application_date} after {date_to}"
            
            # Verify all applications on or before date_to are included
            expected_matches = [app for app in created_apps if app.application_date <= date_to]
            
            result_ids = {app.id for app in results}
            expected_ids = {app.id for app in expected_matches}
            
            assert result_ids == expected_ids, \
                f"Date to filter incomplete: expected {len(expected_ids)} matches, got {len(result_ids)}"


class TestMultipleFilterCompositionProperty:
    """
    Property 15: Multiple Filter Composition
    
    For any combination of filters (search, stage, date range) and any set of
    applications, the results should include only applications matching ALL active
    filter criteria (AND logic).
    
    Validates: Requirement 7.4
    """
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=15),
        search_query=st.text(min_size=1, max_size=50),
        filter_stage=st.sampled_from(Stage),
        date_from=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 12, 31)),
        date_to=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 12, 31))
    )
    @settings(max_examples=20, deadline=None)
    def test_property_15_all_filters_combined(self, requests, search_query, filter_stage, date_from, date_to):
        """
        Feature: job-application-tracker, Property 15: Multiple Filter Composition
        
        All filters combined should use AND logic (all criteria must match).
        
        Validates: Requirement 7.4 - Multiple filter composition
        """
        # Ensure we have at least 10 applications and valid date range
        assume(len(requests) >= 10)
        assume(date_from <= date_to)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Apply all filters
            filters = ApplicationFilters(
                search=search_query,
                stage=filter_stage,
                date_from=date_from,
                date_to=date_to
            )
            results = service.list_applications(filters)
            
            # Verify all results match ALL criteria
            search_lower = search_query.lower()
            for app in results:
                # Check search match
                search_matches = (
                    search_lower in app.company_name.lower() or
                    search_lower in app.position_title.lower()
                )
                assert search_matches, \
                    f"Application {app.id} doesn't match search query '{search_query}'"
                
                # Check stage match
                assert app.stage == filter_stage, \
                    f"Application {app.id} has stage {app.stage}, expected {filter_stage}"
                
                # Check date range match
                assert date_from <= app.application_date <= date_to, \
                    f"Application {app.id} date {app.application_date} outside range [{date_from}, {date_to}]"
            
            # Verify all matching applications are included
            expected_matches = [
                app for app in created_apps
                if (search_lower in app.company_name.lower() or search_lower in app.position_title.lower())
                and app.stage == filter_stage
                and date_from <= app.application_date <= date_to
            ]
            
            result_ids = {app.id for app in results}
            expected_ids = {app.id for app in expected_matches}
            
            assert result_ids == expected_ids, \
                f"Combined filters incomplete: expected {len(expected_ids)} matches, got {len(result_ids)}"
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=15),
        search_query=st.text(min_size=1, max_size=50),
        filter_stage=st.sampled_from(Stage)
    )
    @settings(max_examples=20, deadline=None)
    def test_property_15_search_and_stage_combined(self, requests, search_query, filter_stage):
        """
        Feature: job-application-tracker, Property 15: Multiple Filter Composition
        
        Search and stage filters combined should use AND logic.
        
        Validates: Requirement 7.4 - Search and stage composition
        """
        # Ensure we have at least 10 applications
        assume(len(requests) >= 10)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Apply search and stage filters
            filters = ApplicationFilters(search=search_query, stage=filter_stage)
            results = service.list_applications(filters)
            
            # Verify all results match both criteria
            search_lower = search_query.lower()
            for app in results:
                search_matches = (
                    search_lower in app.company_name.lower() or
                    search_lower in app.position_title.lower()
                )
                assert search_matches and app.stage == filter_stage, \
                    f"Application {app.id} doesn't match both search and stage criteria"
            
            # Verify completeness
            expected_matches = [
                app for app in created_apps
                if (search_lower in app.company_name.lower() or search_lower in app.position_title.lower())
                and app.stage == filter_stage
            ]
            
            assert len(results) == len(expected_matches), \
                f"Expected {len(expected_matches)} matches, got {len(results)}"
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=15),
        filter_stage=st.sampled_from(Stage),
        date_from=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 12, 31)),
        date_to=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 12, 31))
    )
    @settings(max_examples=20, deadline=None)
    def test_property_15_stage_and_date_combined(self, requests, filter_stage, date_from, date_to):
        """
        Feature: job-application-tracker, Property 15: Multiple Filter Composition
        
        Stage and date range filters combined should use AND logic.
        
        Validates: Requirement 7.4 - Stage and date composition
        """
        # Ensure we have at least 10 applications and valid date range
        assume(len(requests) >= 10)
        assume(date_from <= date_to)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Apply stage and date filters
            filters = ApplicationFilters(stage=filter_stage, date_from=date_from, date_to=date_to)
            results = service.list_applications(filters)
            
            # Verify all results match both criteria
            for app in results:
                assert app.stage == filter_stage, \
                    f"Application {app.id} has stage {app.stage}, expected {filter_stage}"
                assert date_from <= app.application_date <= date_to, \
                    f"Application {app.id} date outside range"
            
            # Verify completeness
            expected_matches = [
                app for app in created_apps
                if app.stage == filter_stage
                and date_from <= app.application_date <= date_to
            ]
            
            assert len(results) == len(expected_matches), \
                f"Expected {len(expected_matches)} matches, got {len(results)}"


class TestFilterClearReturnsAllProperty:
    """
    Property 16: Filter Clear Returns All
    
    For any set of applications, clearing all filters should return the complete
    set of applications with no filtering applied.
    
    Validates: Requirement 7.5
    """
    
    @given(requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=20))
    @settings(max_examples=20, deadline=None)
    def test_property_16_no_filters_returns_all(self, requests):
        """
        Feature: job-application-tracker, Property 16: Filter Clear Returns All
        
        No filters (all None) should return all applications.
        
        Validates: Requirement 7.5 - Clear filters returns all
        """
        # Ensure we have at least 5 applications
        assume(len(requests) >= 5)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Apply no filters (all None)
            filters = ApplicationFilters(search=None, stage=None, date_from=None, date_to=None)
            results = service.list_applications(filters)
            
            # Should return all applications
            assert len(results) == len(created_apps), \
                f"No filters should return all {len(created_apps)} applications, got {len(results)}"
            
            # Verify all application IDs are present
            result_ids = {app.id for app in results}
            expected_ids = {app.id for app in created_apps}
            
            assert result_ids == expected_ids, \
                "No filters should return all applications"
    
    @given(requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=20))
    @settings(max_examples=20, deadline=None)
    def test_property_16_none_filters_returns_all(self, requests):
        """
        Feature: job-application-tracker, Property 16: Filter Clear Returns All
        
        Passing None as filters should return all applications.
        
        Validates: Requirement 7.5 - None filters returns all
        """
        # Ensure we have at least 5 applications
        assume(len(requests) >= 5)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Apply None filters
            results = service.list_applications(filters=None)
            
            # Should return all applications
            assert len(results) == len(created_apps), \
                f"None filters should return all {len(created_apps)} applications, got {len(results)}"
    
    @given(
        requests=st.lists(valid_application_request_strategy(), min_size=5, max_size=20),
        search_query=st.text(min_size=1, max_size=50),
        filter_stage=st.sampled_from(Stage)
    )
    @settings(max_examples=20, deadline=None)
    def test_property_16_clearing_filters_restores_all(self, requests, search_query, filter_stage):
        """
        Feature: job-application-tracker, Property 16: Filter Clear Returns All
        
        After applying filters, clearing them should restore all applications.
        
        Validates: Requirement 7.5 - Clearing filters restores all
        """
        # Ensure we have at least 5 applications
        assume(len(requests) >= 5)
        
        with temp_service() as service:
            # Create applications
            created_apps = []
            for request in requests:
                app = service.create_application(request)
                created_apps.append(app)
            
            # Apply filters
            filters_active = ApplicationFilters(search=search_query, stage=filter_stage)
            results_filtered = service.list_applications(filters_active)
            
            # Clear filters
            filters_cleared = ApplicationFilters(search=None, stage=None, date_from=None, date_to=None)
            results_cleared = service.list_applications(filters_cleared)
            
            # Should return all applications after clearing
            assert len(results_cleared) == len(created_apps), \
                f"Cleared filters should return all {len(created_apps)} applications, got {len(results_cleared)}"
            
            # Verify filtered results are a subset of all results
            filtered_ids = {app.id for app in results_filtered}
            all_ids = {app.id for app in results_cleared}
            
            assert filtered_ids.issubset(all_ids), \
                "Filtered results should be a subset of all results"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
