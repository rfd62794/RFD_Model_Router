"""ComputeAdapter — base class for GPU compute providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class JobSpec:
    """Specification for a GPU compute job."""
    job_type: str           # "owl_label" | "yolo_train" | "blip2_enrich"
    gpu_type: str           # "NVIDIA RTX A5000" | "NVIDIA RTX 3090"
    gpu_count: int          # always 1 for current jobs
    upload_paths: list[str] # local paths to upload to pod
    script: str             # Python script to execute on pod (as string)
    download_paths: list[str]  # remote paths to download after job
    local_output_dir: str   # local directory for downloaded results
    timeout_minutes: int    # max job runtime before abort
    pip_packages: list[str] # packages to install on pod


@dataclass
class JobResult:
    """Result of a completed GPU compute job."""
    job_type: str
    success: bool
    output_files: list[str]  # local paths of downloaded files
    duration_seconds: float
    cost_usd: float          # estimated cost (hours * rate)
    error: str | None


class ComputeAdapter(ABC):
    @abstractmethod
    def run_job(self, spec: JobSpec) -> JobResult:
        """
        Execute a GPU compute job end-to-end:
        1. Spin up pod
        2. Install dependencies
        3. Upload data
        4. Execute script
        5. Download results
        6. Terminate pod
        Returns JobResult with success status and output file paths.
        """
        ...

    @abstractmethod
    def estimate_cost(self, spec: JobSpec) -> float:
        """Estimate job cost in USD given spec and expected runtime."""
        ...
