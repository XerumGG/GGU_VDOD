"""Structured download job model shared by the UI and the download engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    """Lifecycle states for a single download job."""

    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadJob:
    """Everything known about one queued media item.

    The UI creates jobs; the engine mutates and reports them. Progress fields
    are plain primitives so events can cross thread boundaries cheaply.
    """

    url: str
    title: str = ""
    format: str = "video"  # "video" | "audio"
    quality: str = ""
    output_format: str = ""
    output_dir: str = ""
    status: JobStatus = JobStatus.QUEUED
    error: str = ""
    progress: float = 0.0  # percent 0-100
    speed: str = "0 B/s"
    eta: str = "—"
    transferred: str = "0 B"
    final_file: str = ""
    attempt: int = 0
    extra: dict = field(default_factory=dict)

    def snapshot(self) -> dict:
        """Thread-safe plain-dict view of the job for signal/slot transport."""
        return {
            "url": self.url,
            "title": self.title,
            "format": self.format,
            "quality": self.quality,
            "output_format": self.output_format,
            "output_dir": self.output_dir,
            "status": self.status.value if isinstance(self.status, JobStatus) else str(self.status),
            "error": self.error,
            "progress": self.progress,
            "speed": self.speed,
            "eta": self.eta,
            "transferred": self.transferred,
            "final_file": self.final_file,
            "attempt": self.attempt,
        }

    @property
    def is_terminal(self) -> bool:
        return self.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)


def make_job(url: str, settings: dict) -> DownloadJob:
    """Build a job from the flat settings dict currently produced by the UI."""
    return DownloadJob(
        url=url,
        format=str(settings.get("format", "video")),
        quality=str(settings.get("quality", "")),
        output_format=str(settings.get("output_format", "")),
        output_dir=str(settings.get("output_dir", "")),
    )
