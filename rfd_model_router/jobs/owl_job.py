"""OWLv2 labeling job for RunPod execution."""
from pathlib import Path
from ..adapters.compute_base import JobSpec

OWL_SCRIPT = '''
import sys
sys.path.insert(0, "/workspace")

import os
os.makedirs("/workspace/assets/eic/labels", exist_ok=True)

from owl import run_labeling_pass

result = run_labeling_pass(
    frames_dir="/workspace/assets/eic/frames",
    asset_preset_path="/workspace/presets/eic_assets.yaml",
    labels_dir="/workspace/assets/eic/labels",
    threshold=0.10,
)
print(result)
'''


def build_owl_job_spec(
    frames_dir: str,
    processed_dir: str,
    preset_path: str,
    owl_py_path: str,
    output_dir: str,
    gpu_type: str = "NVIDIA RTX A5000",
    timeout_minutes: int = 30,
) -> JobSpec:
    """
    Build JobSpec for OWLv2 labeling pass.
    Uploads frames, processed sprites, preset, and owl.py.
    Downloads labels directory.
    """
    return JobSpec(
        job_type="owl_label",
        gpu_type=gpu_type,
        gpu_count=1,
        upload_paths=[
            frames_dir,
            processed_dir,
            preset_path,
            owl_py_path,
        ],
        script=OWL_SCRIPT,
        download_paths=["/workspace/assets/eic/labels"],
        local_output_dir=output_dir,
        timeout_minutes=timeout_minutes,
        pip_packages=[
            "transformers",
            "pillow",
            "opencv-python-headless",
            "pyyaml",
        ],
    )
