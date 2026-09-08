"""
CV Service Layer

Provides CRUD operations for CV documents using the FileService.
Implements CV listing, discovery, and management functionality with
proper error handling and business logic validation.
"""

from datetime import datetime
from uuid import uuid4
from typing import List, Optional, Dict, Any
import logging

from ..models.cv_models import CVModel, CVModelV2, CVCreateRequest, CVUpdateRequest, CVListResponse, CVResponse
from ..models.cv_section_models import SectionType, ListItem
from ..models.llm_models import TailoredCVRequest, TailoredCVResult, TailoringLevel, TailoringSuggestion
from .file_service import FileService, FileServiceError, FileNotFoundError
from .cv_migration import migrate_v1_to_v2

logger = logging.getLogger(__name__)


class CVServiceError(Exception):
    """Base exception for CV service operations."""
    pass


class CVNotFoundError(CVServiceError):
    """Raised when a requested CV is not found."""
    pass


class CVValidationError(CVServiceError):
    """Raised when CV data validation fails."""
    pass


class CVService:
    """
    Service layer for CV document management.
    
    Provides high-level CRUD operations for CV documents,
    including creation, retrieval, updating, deletion, and listing.
    """
    
    def __init__(self, file_service: Optional[FileService] = None):
        """
        Initialize CVService with FileService dependency.
        
        Args:
            file_service: FileService instance for file operations
        """
        self.file_service = file_service or FileService()
    
    def create_cv(self, cv_request: CVCreateRequest) -> CVResponse:
        """
        Create a new CV document.
        
        Args:
            cv_request: CV creation request with CV data
            
        Returns:
            CVResponse with created CV and success message
            
        Raises:
            CVValidationError: If CV data is invalid
            CVServiceError: If CV creation fails
        """
        try:
            # Generate unique ID for new CV
            cv_id = self.file_service.generate_cv_id()
            
            # Create CV model with generated ID
            cv_data = CVModel(
                id=cv_id,
                metadata=cv_request.metadata,
                personal_info=cv_request.personal_info,
                summary=cv_request.summary,
                experience=cv_request.experience,
                education=cv_request.education,
                skills=cv_request.skills,
                certifications=cv_request.certifications
            )
            
            # Set creation timestamp
            cv_data.metadata.created_at = datetime.now()
            cv_data.metadata.updated_at = datetime.now()

            # The request shape is still V1, but CVs are stored and returned as
            # V2 sections, so migrate before saving. Returning the V1 model here
            # fails CVResponse validation, which types `cv` as CVModelV2.
            title = cv_data.metadata.title
            cv_v2 = migrate_v1_to_v2(cv_data)

            # Save CV to file system
            self.file_service.save_cv(cv_v2)

            logger.info(f"Successfully created CV {cv_id}: {title}")

            return CVResponse(
                cv=cv_v2,
                message=f"CV '{title}' created successfully"
            )
            
        except FileServiceError as e:
            raise CVServiceError(f"Failed to create CV: {e}")
        except Exception as e:
            raise CVValidationError(f"Invalid CV data: {e}")
    
    def get_cv(self, cv_id: str) -> CVResponse:
        """
        Retrieve a CV document by ID.
        
        Args:
            cv_id: UUID string of the CV to retrieve
            
        Returns:
            CVResponse with CV data
            
        Raises:
            CVNotFoundError: If CV doesn't exist
            CVServiceError: If CV retrieval fails
        """
        try:
            cv_data = self.file_service.load_cv(cv_id)
            
            logger.info(f"Successfully retrieved CV {cv_id}")
            
            return CVResponse(cv=cv_data)
            
        except FileNotFoundError:
            raise CVNotFoundError(f"CV not found: {cv_id}")
        except FileServiceError as e:
            raise CVServiceError(f"Failed to retrieve CV {cv_id}: {e}")
    
    def duplicate_cv(self, cv_id: str, title: Optional[str] = None) -> CVResponse:
        """
        Create an independent copy of a CV.

        Every id is regenerated — the document's and each section's — so that
        editing the copy cannot reach back into the original. Typography and
        the applied template come along, since a duplicate is usually the
        starting point for a variation on the same design.

        Args:
            cv_id: UUID of the CV to copy
            title: Optional title for the copy; defaults to "<name> (copy)"

        Returns:
            CVResponse holding the new CV

        Raises:
            CVNotFoundError: If the source CV doesn't exist
            CVServiceError: If the copy cannot be saved
        """
        try:
            source = self.file_service.load_cv(cv_id)
            duplicate = source.model_copy(deep=True)

            duplicate.id = str(uuid4())
            duplicate.created_at = datetime.now()
            duplicate.updated_at = datetime.now()

            for section in duplicate.sections:
                section.id = str(uuid4())
                # Entries carry their own ids, which must not be shared either.
                entries = getattr(section.content, 'entries', None)
                if isinstance(entries, list):
                    for entry in entries:
                        if hasattr(entry, 'id'):
                            entry.id = str(uuid4())

                if section.type == SectionType.PERSONAL_INFO:
                    current = getattr(section.content, 'cv_title', None)
                    section.content.cv_title = title or f"{current or 'Untitled CV'} (copy)"

            self.file_service.save_cv(duplicate)
            logger.info(f"Duplicated CV {cv_id} as {duplicate.id}")

            return CVResponse(cv=duplicate)

        except FileNotFoundError:
            raise CVNotFoundError(f"CV not found: {cv_id}")
        except FileServiceError as e:
            raise CVServiceError(f"Failed to duplicate CV {cv_id}: {e}")

    def update_cv(self, cv_id: str, cv_request: CVUpdateRequest) -> CVResponse:
        """
        Update an existing CV document.
        
        Args:
            cv_id: UUID string of the CV to update
            cv_request: CV update request with partial CV data
            
        Returns:
            CVResponse with updated CV and success message
            
        Raises:
            CVNotFoundError: If CV doesn't exist
            CVValidationError: If update data is invalid
            CVServiceError: If CV update fails
        """
        try:
            # Load existing CV
            existing_cv = self.file_service.load_cv(cv_id)
            
            # Update fields that are provided in the request
            update_data = cv_request.model_dump(exclude_unset=True)
            
            # Create updated CV data
            updated_cv_dict = existing_cv.model_dump()
            
            # Apply updates
            for field, value in update_data.items():
                if field == "metadata" and value is not None:
                    # Preserve created_at, update updated_at
                    # Handle both dict and Pydantic model
                    if hasattr(value, 'model_dump'):
                        # It's a Pydantic model
                        updated_cv_dict["metadata"].update(value.model_dump())
                    elif isinstance(value, dict):
                        # It's already a dict
                        updated_cv_dict["metadata"].update(value)
                    updated_cv_dict["metadata"]["created_at"] = existing_cv.metadata.created_at
                    updated_cv_dict["metadata"]["updated_at"] = datetime.now()
                else:
                    updated_cv_dict[field] = value
            
            # Ensure updated_at is set
            updated_cv_dict["metadata"]["updated_at"] = datetime.now()
            
            # Create new CV model with updates
            updated_cv = CVModel(**updated_cv_dict)
            
            # Save updated CV
            self.file_service.save_cv(updated_cv)
            
            logger.info(f"Successfully updated CV {cv_id}: {updated_cv.metadata.title}")
            
            return CVResponse(
                cv=updated_cv,
                message=f"CV '{updated_cv.metadata.title}' updated successfully"
            )
            
        except FileNotFoundError:
            raise CVNotFoundError(f"CV not found: {cv_id}")
        except FileServiceError as e:
            raise CVServiceError(f"Failed to update CV {cv_id}: {e}")
        except Exception as e:
            raise CVValidationError(f"Invalid update data: {e}")
    
    def delete_cv(self, cv_id: str) -> CVResponse:
        """
        Delete a CV document.
        
        Args:
            cv_id: UUID string of the CV to delete
            
        Returns:
            CVResponse with success message
            
        Raises:
            CVNotFoundError: If CV doesn't exist
            CVServiceError: If CV deletion fails
        """
        try:
            # Load CV to get title for response message
            cv_data = self.file_service.load_cv(cv_id)
            
            # Get title - handle both V1 and V2 formats
            if hasattr(cv_data, 'metadata'):
                cv_title = cv_data.metadata.title
            else:
                # V2 CV - extract title from personal_info section
                cv_title = "Untitled CV"
                personal_section = cv_data.get_section_by_type("personal_info")
                if personal_section and hasattr(personal_section.content, 'full_name'):
                    cv_title = personal_section.content.full_name
            
            # Delete CV file
            self.file_service.delete_cv(cv_id)
            
            logger.info(f"Successfully deleted CV {cv_id}: {cv_title}")
            
            return CVResponse(
                cv=cv_data,  # Return deleted CV data for confirmation
                message=f"CV '{cv_title}' deleted successfully"
            )
            
        except FileNotFoundError:
            raise CVNotFoundError(f"CV not found: {cv_id}")
        except FileServiceError as e:
            raise CVServiceError(f"Failed to delete CV {cv_id}: {e}")
    
    def list_cvs(self) -> CVListResponse:
        """
        List all CV documents.
        
        Returns:
            CVListResponse with list of all CVs and total count
            
        Raises:
            CVServiceError: If CV listing fails
        """
        try:
            # Get all CV file IDs
            cv_ids = self.file_service.list_cv_files()
            
            # Load all CVs
            cvs = []
            failed_loads = []
            
            for cv_id in cv_ids:
                try:
                    cv_data = self.file_service.load_cv(cv_id)
                    cvs.append(cv_data)
                except FileServiceError as e:
                    # Log failed loads but continue with others
                    logger.warning(f"Failed to load CV {cv_id}: {e}")
                    failed_loads.append(cv_id)
            
            # Sort CVs by updated_at (most recent first)
            # Handle both V1 (has metadata.updated_at) and V2 (has updated_at directly)
            def get_updated_at(cv):
                if hasattr(cv, 'metadata'):
                    return cv.metadata.updated_at
                else:
                    return cv.updated_at
            
            cvs.sort(key=get_updated_at, reverse=True)
            
            logger.info(f"Successfully listed {len(cvs)} CVs")
            if failed_loads:
                logger.warning(f"Failed to load {len(failed_loads)} CVs: {failed_loads}")
            
            return CVListResponse(
                cvs=cvs,
                total=len(cvs)
            )
            
        except FileServiceError as e:
            raise CVServiceError(f"Failed to list CVs: {e}")
    
    def cv_exists(self, cv_id: str) -> bool:
        """
        Check if a CV exists.
        
        Args:
            cv_id: UUID string of the CV to check
            
        Returns:
            True if CV exists, False otherwise
        """
        return self.file_service.cv_exists(cv_id)
    
    def discover_cvs(self) -> CVListResponse:
        """
        Discover and load CV files from the filesystem.
        
        This method scans the CV directory for JSON files and attempts
        to load them as CV documents. Useful for detecting CVs that
        were added outside the application.
        
        Returns:
            CVListResponse with discovered CVs
            
        Raises:
            CVServiceError: If discovery fails
        """
        try:
            logger.info("Starting CV discovery process")
            
            # Use the regular list_cvs method which already handles discovery
            return self.list_cvs()
            
        except CVServiceError:
            raise
        except Exception as e:
            raise CVServiceError(f"CV discovery failed: {e}")
    
    def get_cv_summary(self, cv_id: str) -> dict:
        """
        Get a summary of CV information without loading full data.
        
        Args:
            cv_id: UUID string of the CV
            
        Returns:
            Dictionary with CV summary information
            
        Raises:
            CVNotFoundError: If CV doesn't exist
            CVServiceError: If summary retrieval fails
        """
        try:
            # Check if CV exists
            if not self.file_service.cv_exists(cv_id):
                raise CVNotFoundError(f"CV not found: {cv_id}")
            
            # Get metadata from metadata file
            metadata = self.file_service.get_metadata()
            cv_metadata = metadata.get(cv_id, {})
            
            # If not in metadata, load CV to get basic info
            if not cv_metadata:
                cv_data = self.file_service.load_cv(cv_id)
                cv_metadata = {
                    "title": cv_data.metadata.title,
                    "file_path": f"{cv_id}.json"
                }
            
            return {
                "id": cv_id,
                "title": cv_metadata.get("title", "Untitled CV"),
                "file_path": cv_metadata.get("file_path", f"{cv_id}.json")
            }
            
        except FileNotFoundError:
            raise CVNotFoundError(f"CV not found: {cv_id}")
        except FileServiceError as e:
            raise CVServiceError(f"Failed to get CV summary {cv_id}: {e}")
    
    def create_tailored_cv(
        self,
        request: TailoredCVRequest,
        tailoring_suggestions: List[TailoringSuggestion]
    ) -> TailoredCVResult:
        """
        Create a new CV variant tailored to a specific job description.
        
        This method creates a new CV by applying tailoring suggestions to a source CV
        based on the specified tailoring level. The original CV is preserved unchanged.
        
        Args:
            request: TailoredCVRequest with source CV ID, job description, and tailoring settings
            tailoring_suggestions: List of TailoringSuggestion objects from job tailoring analysis
            
        Returns:
            TailoredCVResult with the new tailored CV and applied changes
            
        Raises:
            CVNotFoundError: If source CV doesn't exist
            CVValidationError: If tailoring fails
            CVServiceError: If CV creation fails
        """
        try:
            source_cv = self.file_service.load_cv(request.source_cv_id)

            # `load_cv` migrates legacy V1 files on read, so every CV that
            # reaches here is a V2 sections model.
            return self._create_tailored_cv_v2(
                source_cv, request, tailoring_suggestions
            )

        except FileNotFoundError:
            raise CVNotFoundError(f"Source CV not found: {request.source_cv_id}")
        except FileServiceError as e:
            raise CVServiceError(f"Failed to create tailored CV: {e}")
        except Exception as e:
            raise CVValidationError(f"Failed to apply tailoring: {e}")

    def _create_tailored_cv_v2(
        self,
        source_cv: CVModelV2,
        request: TailoredCVRequest,
        tailoring_suggestions: List[TailoringSuggestion]
    ) -> TailoredCVResult:
        """
        Create a tailored copy of a V2 (sections-based) CV.

        V2 CVs hold their content inside typed sections rather than the flat
        fields of V1, so suggestions are applied to section content directly and
        the CV title lives on the personal-info section rather than in metadata.

        Args:
            source_cv: The V2 CV to tailor
            request: Tailoring request with the target title and preserved sections
            tailoring_suggestions: Suggestions to consider applying

        Returns:
            TailoredCVResult with the new CV and the changes that were applied
        """
        tailored_cv = source_cv.model_copy(deep=True)
        tailored_cv.id = self.file_service.generate_cv_id()
        tailored_cv.created_at = datetime.now()
        tailored_cv.updated_at = datetime.now()

        changes_applied: List[str] = []
        preserve_sections = set(request.preserve_sections or [])

        applicable_suggestions = self._filter_suggestions_by_level(
            tailoring_suggestions,
            request.tailoring_level
        )

        for suggestion in applicable_suggestions:
            if suggestion.section in preserve_sections:
                logger.info(
                    f"Skipping suggestion for preserved section: {suggestion.section}"
                )
                continue

            if self._apply_tailoring_suggestion_v2(tailored_cv, suggestion):
                change_description = (
                    f"{suggestion.section}: {suggestion.reason} "
                    f"(Priority: {suggestion.priority.value})"
                )
                changes_applied.append(change_description)
                logger.info(f"Applied tailoring suggestion: {change_description}")

        # The CV title lives on the personal-info section in V2.
        self._set_v2_cv_title(tailored_cv, request.target_cv_title)

        self.file_service.save_cv(tailored_cv)

        match_score = min(100.0, 60.0 + (len(changes_applied) * 5.0))

        logger.info(
            f"Successfully created tailored CV {tailored_cv.id} from source "
            f"{request.source_cv_id} with {len(changes_applied)} changes applied"
        )

        return TailoredCVResult(
            source_cv_id=request.source_cv_id,
            tailored_cv_id=tailored_cv.id,
            tailored_cv=tailored_cv.model_dump(),
            changes_applied=changes_applied,
            tailoring_level=request.tailoring_level,
            match_score=match_score,
            created_at=datetime.now()
        )

    def _set_v2_cv_title(self, cv: CVModelV2, title: Optional[str]) -> None:
        """Set the CV title on the personal-info section, if there is one."""
        if not title:
            return

        for section in cv.sections:
            if section.type == SectionType.PERSONAL_INFO:
                section.content.cv_title = title
                return

        logger.warning(
            f"CV {cv.id} has no personal_info section; tailored title not stored"
        )

    def _apply_tailoring_suggestion_v2(
        self,
        cv: CVModelV2,
        suggestion: TailoringSuggestion
    ) -> bool:
        """
        Apply a single tailoring suggestion to a V2 CV.

        Args:
            cv: CV to modify in place
            suggestion: Tailoring suggestion to apply

        Returns:
            True if the suggestion changed something, False otherwise
        """
        try:
            section_name = suggestion.section.lower()

            if section_name in ("summary", "professional_summary"):
                target_types = (SectionType.SUMMARY,)
            elif "experience" in section_name:
                target_types = (SectionType.EXPERIENCE,)
            elif "skills" in section_name:
                target_types = (SectionType.SKILLS,)
            elif "education" in section_name:
                target_types = (SectionType.EDUCATION,)
            else:
                logger.warning(f"Unknown section type for tailoring: {section_name}")
                return False

            for section in cv.sections:
                if section.type not in target_types:
                    continue

                content_type = getattr(section.content, "content_type", None)

                if content_type == "free_text":
                    section.content.text = suggestion.suggested
                    return True

                if content_type == "list":
                    existing = {item.text for item in section.content.items}
                    added = [kw for kw in suggestion.keywords_added if kw not in existing]
                    if added:
                        section.content.items.extend(ListItem(text=kw) for kw in added)
                        return True

                if content_type == "structured":
                    if self._apply_to_structured_entries(section.content, suggestion):
                        return True

            return False

        except Exception as e:
            logger.error(f"Failed to apply suggestion for {suggestion.section}: {e}")
            return False

    def _apply_to_structured_entries(
        self,
        content: Any,
        suggestion: TailoringSuggestion
    ) -> bool:
        """Replace the suggestion's current text within a structured section's entries."""
        for entry in content.entries:
            description = getattr(entry, "description", None)
            if description and suggestion.current in description:
                entry.description = description.replace(
                    suggestion.current,
                    suggestion.suggested
                )
                return True

            achievements = getattr(entry, "achievements", None)
            if achievements:
                for i, achievement in enumerate(achievements):
                    if suggestion.current in achievement:
                        achievements[i] = achievement.replace(
                            suggestion.current,
                            suggestion.suggested
                        )
                        return True

        return False

    def _filter_suggestions_by_level(
        self,
        suggestions: List[TailoringSuggestion],
        level: TailoringLevel
    ) -> List[TailoringSuggestion]:
        """
        Filter tailoring suggestions based on the tailoring level.
        
        Args:
            suggestions: List of all tailoring suggestions
            level: Tailoring level (conservative, moderate, aggressive)
            
        Returns:
            Filtered list of suggestions to apply
        """
        if level == TailoringLevel.CONSERVATIVE:
            # Only apply high priority suggestions
            return [s for s in suggestions if s.priority.value == "high"]
        elif level == TailoringLevel.MODERATE:
            # Apply high and medium priority suggestions
            return [s for s in suggestions if s.priority.value in ["high", "medium"]]
        else:  # AGGRESSIVE
            # Apply all suggestions
            return suggestions
    
