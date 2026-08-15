"""
Attempt record dataclass for tracking AI provider generation attempts.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class AttemptRecord:
    attempt_id: str
    key_id: str
    model: str
    status_code: int
    classification: str
    success: bool
    latency_ms: Optional[int] = 0

    def to_dict(self) -> dict:
        return {
            "attempt_id": self.attempt_id,
            "key_id": self.key_id,
            "model": self.model,
            "status_code": self.status_code,
            "classification": self.classification,
            "success": self.success
        }
