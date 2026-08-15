"""
Pipeline exception definitions for Textline.
"""

class NoAvailableModelError(RuntimeError):
    """Exception raised when no usable Gemini model/key combination is available."""
    def __init__(self, message, error_code="NO_AVAILABLE_MODEL"):
        super().__init__(message)
        self.error_code = error_code

class PipelineTimeoutError(RuntimeError):
    """Exception raised when a pipeline stage exceeds its explicit timeout."""
    def __init__(self, message, error_code="TIMEOUT"):
        super().__init__(message)
        self.error_code = error_code
