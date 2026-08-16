"""
Configuration constants for Textline application.
"""

DEFAULT_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-flash-latest"
]

# Supported Gemini models for matrix diagnostic testing and fallback tracking
SUPPORTED_HEALTH_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
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
