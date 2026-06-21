"""RunpodAdapter — GPU compute jobs via RunPod SDK."""
import os
import time
import tempfile
import shutil
from pathlib import Path

from .compute_base import ComputeAdapter, JobSpec, JobResult

# GPU type → hourly rate (Community Cloud, approximate)
GPU_RATES = {
    "NVIDIA RTX A5000": 0.27,
    "NVIDIA RTX 3090": 0.22,
    "NVIDIA RTX 4090": 0.34,
    "NVIDIA RTX A6000": 0.49,
}

DEFAULT_GPU = "NVIDIA RTX A5000"
POD_IMAGE = "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404"
DEFAULT_RATE = 0.50  # Fallback rate for unknown GPU types


class RunpodAdapter(ComputeAdapter):
    def __init__(self, api_key: str | None = None):
        """
        Initialize RunPod adapter.
        api_key defaults to RUNPOD_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("RUNPOD_API_KEY")
        if not self.api_key:
            raise ValueError("RUNPOD_API_KEY must be set via environment or constructor argument")
        self._client = None

    def _get_client(self):
        """Return configured runpod module. Lazy import."""
        if self._client is None:
            import runpod
            self._client = runpod.APIKeyAuth(api_key=self.api_key)
        return self._client

    def _wait_for_pod(self, pod_id: str, timeout_seconds: int = 120) -> bool:
        """
        Poll pod status until RUNNING or timeout.
        Returns True if pod reached RUNNING state.
        """
        client = self._get_client()
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            try:
                pod = client.get_pod(pod_id)
                status = pod.get("desiredState", "")
                if status == "RUNNING":
                    return True
                time.sleep(2)
            except Exception:
                time.sleep(2)
                continue
        
        return False

    def _install_packages(self, pod_id: str, packages: list[str]) -> bool:
        """Run pip install on pod. Returns True on success."""
        client = self._get_client()
        try:
            if not packages:
                return True
            
            pip_cmd = f"pip install {' '.join(packages)}"
            client.execute_pod_command(
                pod_id,
                command=pip_cmd,
                container_name="pytorch",
            )
            return True
        except Exception:
            return False

    def _upload_paths(self, pod_id: str, local_paths: list[str]) -> bool:
        """
        Upload local files/directories to pod /workspace/.
        Returns True on success.
        """
        client = self._get_client()
        try:
            for path in local_paths:
                local_path = Path(path)
                if local_path.is_file():
                    client.upload_file_to_pod(
                        pod_id,
                        source_path=str(local_path),
                        destination_path=f"/workspace/{local_path.name}",
                    )
                elif local_path.is_dir():
                    client.upload_directory_to_pod(
                        pod_id,
                        source_path=str(local_path),
                        destination_path=f"/workspace/{local_path.name}",
                    )
            return True
        except Exception:
            return False

    def _run_script(self, pod_id: str, script: str, timeout_minutes: int) -> bool:
        """
        Write script to pod and execute it.
        Returns True if script exits 0.
        """
        client = self._get_client()
        try:
            # Write script to file
            client.execute_pod_command(
                pod_id,
                command=f"echo '{script}' > /workspace/job_script.py",
                container_name="pytorch",
            )
            
            # Execute script
            result = client.execute_pod_command(
                pod_id,
                command="python /workspace/job_script.py",
                container_name="pytorch",
                timeout=timeout_minutes * 60,
            )
            
            return result.get("exitCode", -1) == 0
        except Exception:
            return False

    def _download_paths(
        self,
        pod_id: str,
        remote_paths: list[str],
        local_output_dir: str,
    ) -> list[str]:
        """
        Download remote paths from pod to local_output_dir.
        Returns list of local file paths downloaded.
        """
        client = self._get_client()
        downloaded = []
        output_dir = Path(local_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            for remote_path in remote_paths:
                local_path = output_dir / Path(remote_path).name
                client.download_file_from_pod(
                    pod_id,
                    source_path=remote_path,
                    destination_path=str(local_path),
                )
                downloaded.append(str(local_path))
        except Exception:
            pass
        
        return downloaded

    def _terminate_pod(self, pod_id: str) -> None:
        """Terminate pod. Always called — even on failure."""
        client = self._get_client()
        try:
            client.stop_pod(pod_id)
        except Exception:
            pass

    def run_job(self, spec: JobSpec) -> JobResult:
        """
        Execute GPU compute job end-to-end.
        Pod is always terminated in finally block — never left running.
        """
        pod_id = None
        start_time = time.time()
        error = None
        output_files = []
        
        try:
            client = self._get_client()
            
            # Spin up pod
            pod = client.create_pod(
                name=f"rfd-{spec.job_type}-{int(time.time())}",
                image_name=POD_IMAGE,
                gpu_type_id=spec.gpu_type,
                gpu_count=spec.gpu_count,
                volume_size=20,  # GB
            )
            pod_id = pod.get("id")
            
            if not pod_id:
                raise RuntimeError("Failed to create pod")
            
            # Wait for pod to be ready
            if not self._wait_for_pod(pod_id):
                raise RuntimeError("Pod failed to reach RUNNING state")
            
            # Install packages
            if not self._install_packages(pod_id, spec.pip_packages):
                raise RuntimeError("Failed to install packages")
            
            # Upload data
            if not self._upload_paths(pod_id, spec.upload_paths):
                raise RuntimeError("Failed to upload data")
            
            # Run script
            if not self._run_script(pod_id, spec.script, spec.timeout_minutes):
                raise RuntimeError("Script execution failed")
            
            # Download results
            output_files = self._download_paths(
                pod_id,
                spec.download_paths,
                spec.local_output_dir,
            )
            
            duration = time.time() - start_time
            cost = self.estimate_cost(spec)
            
            return JobResult(
                job_type=spec.job_type,
                success=True,
                output_files=output_files,
                duration_seconds=duration,
                cost_usd=cost,
                error=None,
            )
            
        except Exception as e:
            duration = time.time() - start_time
            cost = self.estimate_cost(spec)
            error_msg = str(e)
            
            return JobResult(
                job_type=spec.job_type,
                success=False,
                output_files=output_files,
                duration_seconds=duration,
                cost_usd=cost,
                error=error_msg,
            )
        finally:
            if pod_id:
                self._terminate_pod(pod_id)

    def estimate_cost(self, spec: JobSpec) -> float:
        """Estimate cost: hourly_rate * (timeout_minutes / 60)."""
        hourly_rate = GPU_RATES.get(spec.gpu_type, DEFAULT_RATE)
        hours = spec.timeout_minutes / 60
        return hourly_rate * hours
