"""
Configuration constants for Textline application.
"""

DEFAULT_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-lite-latest",
    "gemini-flash-latest"
]

# Supported Gemini models for matrix diagnostic testing and fallback tracking
SUPPORTED_HEALTH_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-lite-latest",
    "gemini-flash-latest"
]


# Project Metadata Mapping (associates safe key IDs to separate project metadata)
PROJECT_METADATA_MAP = {
    "1_textline_gemini_9838_AlReasoningValidationSystem": {
        "project_number": "333673007466",
        "project_name": "textline_gemini_9838_AlReasoningValidationSystem"
    },
    "2_textline_gemini_9838_AcademicUniverseService": {
        "project_number": "500719954463",
        "project_name": "textline_gemini_9838_AcademicUniverseService"
    }
}
