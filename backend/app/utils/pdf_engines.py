"""
PDF Engine Detection and Management

Provides detection and fallback logic for PDF engines used in CV export.
Supports xelatex and tectonic engines with automatic fallback capabilities.
"""

import subprocess
import logging
from enum import Enum
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PDFEngine(Enum):
    """Supported PDF engines for LaTeX compilation."""
    XELATEX = "xelatex"
    TECTONIC = "tectonic"


@dataclass
class EngineInfo:
    """Information about a PDF engine."""
    engine: PDFEngine
    available: bool
    version: Optional[str] = None
    path: Optional[str] = None
    error_message: Optional[str] = None


class PDFEngineDetector:
    """
    Detects available PDF engines and provides fallback logic.
    
    Checks for xelatex and tectonic availability and provides
    automatic fallback between engines when one fails.
    """
    
    def __init__(self):
        """Initialize the PDF engine detector."""
        self._engine_cache: Dict[PDFEngine, EngineInfo] = {}
        self._preferred_order = [PDFEngine.XELATEX, PDFEngine.TECTONIC]
    
    def detect_engines(self, force_refresh: bool = False) -> Dict[PDFEngine, EngineInfo]:
        """
        Detect all available PDF engines.
        
        Args:
            force_refresh: If True, bypass cache and re-detect engines
            
        Returns:
            Dictionary mapping engines to their availability information
        """
        if not force_refresh and self._engine_cache:
            return self._engine_cache.copy()
        
        self._engine_cache.clear()
        
        for engine in PDFEngine:
            self._engine_cache[engine] = self._detect_single_engine(engine)
        
        logger.info(f"Detected PDF engines: {self._get_available_engines()}")
        return self._engine_cache.copy()
    
    def _detect_single_engine(self, engine: PDFEngine) -> EngineInfo:
        """
        Detect a single PDF engine.
        
        Args:
            engine: The engine to detect
            
        Returns:
            EngineInfo with detection results
        """
        try:
            # Try to get version information
            result = subprocess.run(
                [engine.value, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Extract version from output
                version = self._extract_version(engine, result.stdout)
                
                # Get engine path
                path_result = subprocess.run(
                    ["which", engine.value],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                path = path_result.stdout.strip() if path_result.returncode == 0 else None
                
                return EngineInfo(
                    engine=engine,
                    available=True,
                    version=version,
                    path=path
                )
            else:
                return EngineInfo(
                    engine=engine,
                    available=False,
                    error_message=f"Command failed with code {result.returncode}: {result.stderr.strip()}"
                )
                
        except subprocess.TimeoutExpired:
            return EngineInfo(
                engine=engine,
                available=False,
                error_message="Command timed out"
            )
        except FileNotFoundError:
            return EngineInfo(
                engine=engine,
                available=False,
                error_message="Engine not found in PATH"
            )
        except Exception as e:
            return EngineInfo(
                engine=engine,
                available=False,
                error_message=f"Detection failed: {str(e)}"
            )
    
    def _extract_version(self, engine: PDFEngine, version_output: str) -> Optional[str]:
        """
        Extract version information from engine output.
        
        Args:
            engine: The PDF engine
            version_output: Raw version command output
            
        Returns:
            Extracted version string or None if not found
        """
        try:
            lines = version_output.strip().split('\n')
            if not lines:
                return None
            
            first_line = lines[0]
            
            if engine == PDFEngine.XELATEX:
                # XeLaTeX output format: "XeTeX 3.141592653-2.6-0.999993 (TeX Live 2022)"
                if "XeTeX" in first_line:
                    parts = first_line.split()
                    if len(parts) >= 2:
                        return parts[1]
            
            elif engine == PDFEngine.TECTONIC:
                # Tectonic output format: "Tectonic 0.8.0"
                if "Tectonic" in first_line:
                    parts = first_line.split()
                    if len(parts) >= 2:
                        return parts[1]
            
            # Fallback: return first line if no specific parsing worked
            return first_line
            
        except Exception as e:
            logger.warning(f"Failed to extract version for {engine.value}: {e}")
            return None
    
    def get_available_engines(self) -> List[PDFEngine]:
        """
        Get list of available PDF engines.
        
        Returns:
            List of available engines in preferred order
        """
        if not self._engine_cache:
            self.detect_engines()
        
        return [
            engine for engine in self._preferred_order
            if self._engine_cache.get(engine, EngineInfo(engine, False)).available
        ]
    
    def _get_available_engines(self) -> List[str]:
        """Get available engine names for logging."""
        return [engine.value for engine in self.get_available_engines()]
    
    def get_preferred_engine(self) -> Optional[PDFEngine]:
        """
        Get the preferred available PDF engine.
        
        Returns:
            The most preferred available engine, or None if none available
        """
        available = self.get_available_engines()
        return available[0] if available else None
    
    def get_fallback_engine(self, failed_engine: PDFEngine) -> Optional[PDFEngine]:
        """
        Get a fallback engine when the specified engine fails.
        
        Args:
            failed_engine: The engine that failed
            
        Returns:
            Alternative engine to try, or None if no alternatives
        """
        available = self.get_available_engines()
        
        # Remove the failed engine from available options
        fallback_options = [engine for engine in available if engine != failed_engine]
        
        return fallback_options[0] if fallback_options else None
    
    def validate_engine_requirements(self) -> Tuple[bool, List[str]]:
        """
        Validate that at least one PDF engine is available.
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        available = self.get_available_engines()
        
        if not available:
            issues = []
            for engine in PDFEngine:
                engine_info = self._engine_cache.get(engine)
                if engine_info and engine_info.error_message:
                    issues.append(f"{engine.value}: {engine_info.error_message}")
                else:
                    issues.append(f"{engine.value}: Not detected")
            
            return False, issues
        
        return True, []
    
    def get_engine_info(self, engine: PDFEngine) -> Optional[EngineInfo]:
        """
        Get detailed information about a specific engine.
        
        Args:
            engine: The engine to get information for
            
        Returns:
            EngineInfo for the engine, or None if not detected
        """
        if not self._engine_cache:
            self.detect_engines()
        
        return self._engine_cache.get(engine)
    
    def test_engine_compilation(self, engine: PDFEngine) -> Tuple[bool, Optional[str]]:
        """
        Test if an engine can successfully compile a minimal LaTeX document.
        
        Args:
            engine: The engine to test
            
        Returns:
            Tuple of (success, error_message)
        """
        engine_info = self.get_engine_info(engine)
        if not engine_info or not engine_info.available:
            return False, f"Engine {engine.value} is not available"
        
        # Minimal LaTeX document for testing
        test_latex = r"""
\documentclass{article}
\begin{document}
Test document for PDF engine validation.
\end{document}
"""
        
        try:
            import tempfile
            import os
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write test LaTeX file
                tex_file = os.path.join(temp_dir, "test.tex")
                with open(tex_file, 'w', encoding='utf-8') as f:
                    f.write(test_latex)
                
                # Try to compile
                result = subprocess.run(
                    [engine.value, "-interaction=nonstopmode", "-output-directory", temp_dir, tex_file],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=temp_dir
                )
                
                # Check if PDF was generated
                pdf_file = os.path.join(temp_dir, "test.pdf")
                if result.returncode == 0 and os.path.exists(pdf_file):
                    return True, None
                else:
                    error_msg = result.stderr.strip() if result.stderr else "Compilation failed"
                    return False, f"Compilation test failed: {error_msg}"
                    
        except subprocess.TimeoutExpired:
            return False, "Compilation test timed out"
        except Exception as e:
            return False, f"Compilation test error: {str(e)}"


# Global detector instance
_detector_instance: Optional[PDFEngineDetector] = None


def get_pdf_engine_detector() -> PDFEngineDetector:
    """
    Get the global PDF engine detector instance.
    
    Returns:
        Singleton PDFEngineDetector instance
    """
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = PDFEngineDetector()
    return _detector_instance


def detect_available_engines(force_refresh: bool = False) -> Dict[PDFEngine, EngineInfo]:
    """
    Convenience function to detect available PDF engines.
    
    Args:
        force_refresh: If True, bypass cache and re-detect engines
        
    Returns:
        Dictionary mapping engines to their availability information
    """
    return get_pdf_engine_detector().detect_engines(force_refresh)


def get_preferred_pdf_engine() -> Optional[PDFEngine]:
    """
    Convenience function to get the preferred PDF engine.
    
    Returns:
        The most preferred available engine, or None if none available
    """
    return get_pdf_engine_detector().get_preferred_engine()


def validate_pdf_engine_availability() -> Tuple[bool, List[str]]:
    """
    Convenience function to validate PDF engine requirements.
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    return get_pdf_engine_detector().validate_engine_requirements()