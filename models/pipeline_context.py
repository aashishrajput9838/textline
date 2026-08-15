"""
Pipeline context dataclass holding execution state for a single screenshot processing pipeline run.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time

@dataclass
class PipelineContext:
    pipeline_id: str
    started_at: float = field(default_factory=time.time)
    stage: str = "IDLE"
    status: str = "idle"  # idle | processing | success | error
    image: Optional[Any] = None
    image_hash: Optional[str] = None
    image_b64_url: Optional[str] = None
    selected_key: Optional[str] = None
    selected_model: Optional[str] = None
    provider: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    answer: Optional[str] = None
    attempts_breakdown: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timings: Dict[str, int] = field(default_factory=dict)

    def elapsed_ms(self) -> int:
        return int((time.time() - self.started_at) * 1000)
