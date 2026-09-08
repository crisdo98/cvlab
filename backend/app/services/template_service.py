"""
Template Service

Service for managing custom typography templates with file-based persistence.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from ..models.typography_models import TypographyTemplate, TypographyConfig

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for managing custom typography templates."""
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize template service.
        
        Args:
            data_dir: Base data directory (defaults to ./data)
        """
        if data_dir is None:
            data_dir = Path("data")
        
        self.data_dir = Path(data_dir)
        self.templates_dir = self.data_dir / "templates"
        self.templates_file = self.templates_dir / "custom_templates.json"
        
        # Ensure directories exist
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # Load custom templates
        self._custom_templates: Dict[str, TypographyTemplate] = {}
        self._load_custom_templates()
    
    def _load_custom_templates(self) -> None:
        """Load custom templates from file."""
        try:
            if self.templates_file.exists():
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for template_data in data.get('templates', []):
                    template = TypographyTemplate(**template_data)
                    self._custom_templates[template.id] = template
                    
                logger.info(f"Loaded {len(self._custom_templates)} custom templates")
        except Exception as e:
            logger.error(f"Failed to load custom templates: {e}")
            self._custom_templates = {}
    
    def _save_custom_templates(self) -> None:
        """Save custom templates to file."""
        try:
            data = {
                'templates': [
                    template.model_dump() for template in self._custom_templates.values()
                ],
                'updated_at': datetime.utcnow().isoformat()
            }
            
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Saved {len(self._custom_templates)} custom templates")
        except Exception as e:
            logger.error(f"Failed to save custom templates: {e}")
            raise
    
    def get_custom_template(self, template_id: str) -> Optional[TypographyTemplate]:
        """
        Get a custom template by ID.
        
        Args:
            template_id: Template identifier
            
        Returns:
            Template if found, None otherwise
        """
        return self._custom_templates.get(template_id)
    
    def list_custom_templates(self) -> List[TypographyTemplate]:
        """
        List all custom templates.
        
        Returns:
            List of custom templates
        """
        return list(self._custom_templates.values())
    
    def save_template(
        self,
        name: str,
        description: str,
        typography: TypographyConfig,
        template_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> TypographyTemplate:
        """
        Save a custom template.
        
        Args:
            name: Template name
            description: Template description
            typography: Typography configuration
            template_id: Optional custom ID (generated from name if not provided)
            tags: Optional tags for categorization
            
        Returns:
            Created template
            
        Raises:
            ValueError: If template ID already exists
        """
        # Generate template ID if not provided
        if template_id is None:
            template_id = self._generate_template_id(name)
        
        # Check if template already exists
        if template_id in self._custom_templates:
            raise ValueError(f"Template with ID '{template_id}' already exists")
        
        # Create template
        template = TypographyTemplate(
            id=template_id,
            name=name,
            description=description,
            typography=typography,
            tags=tags or ["custom"]
        )
        
        # Save to memory and file
        self._custom_templates[template_id] = template
        self._save_custom_templates()
        
        logger.info(f"Saved custom template: {template_id}")
        
        return template
    
    def update_template(
        self,
        template_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        typography: Optional[TypographyConfig] = None,
        tags: Optional[List[str]] = None
    ) -> TypographyTemplate:
        """
        Update an existing custom template.
        
        Args:
            template_id: Template identifier
            name: New name (optional)
            description: New description (optional)
            typography: New typography config (optional)
            tags: New tags (optional)
            
        Returns:
            Updated template
            
        Raises:
            ValueError: If template not found
        """
        if template_id not in self._custom_templates:
            raise ValueError(f"Template not found: {template_id}")
        
        template = self._custom_templates[template_id]
        
        # Update fields
        if name is not None:
            template.name = name
        if description is not None:
            template.description = description
        if typography is not None:
            template.typography = typography
        if tags is not None:
            template.tags = tags
        
        # Save changes
        self._save_custom_templates()
        
        logger.info(f"Updated custom template: {template_id}")
        
        return template
    
    def delete_template(self, template_id: str) -> None:
        """
        Delete a custom template.
        
        Args:
            template_id: Template identifier
            
        Raises:
            ValueError: If template not found
        """
        if template_id not in self._custom_templates:
            raise ValueError(f"Template not found: {template_id}")
        
        del self._custom_templates[template_id]
        self._save_custom_templates()
        
        logger.info(f"Deleted custom template: {template_id}")
    
    def _generate_template_id(self, name: str) -> str:
        """
        Generate a template ID from name.
        
        Args:
            name: Template name
            
        Returns:
            Generated template ID
        """
        # Convert to lowercase, replace spaces and special chars with underscores
        template_id = name.lower()
        template_id = ''.join(c if c.isalnum() else '_' for c in template_id)
        template_id = '_'.join(filter(None, template_id.split('_')))  # Remove consecutive underscores
        
        # Ensure uniqueness by appending number if needed
        base_id = template_id
        counter = 1
        while template_id in self._custom_templates:
            template_id = f"{base_id}_{counter}"
            counter += 1
        
        return template_id
