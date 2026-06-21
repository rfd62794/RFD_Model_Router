"""YOLO nano training job for RunPod execution."""
from ..adapters.compute_base import JobSpec

YOLO_SCRIPT = '''
from pathlib import Path
from ultralytics import YOLO

DATASET_YAML = """
path: /workspace/assets/eic
train: frames
val: frames
nc: 13
names:
  0: Darwin
  1: Aquaconda
  2: Shellephant
  3: Crabtaur
  4: Crabbybara
  5: HatBirb
  6: Krabaroo
  7: Pantther
  8: Pilferret
  9: Sandshark
  10: SnowHare
  11: Spiderfrog
  12: Turtoid
"""

dataset_path = Path("/workspace/assets/eic/dataset.yaml")
dataset_path.write_text(DATASET_YAML)

model = YOLO("yolov8n.pt")
results = model.train(
    data=str(dataset_path),
    epochs=50,
    imgsz=640,
    batch=16,
    device=0,
    project="/workspace/assets/eic/models",
    name="yolo_eic",
    patience=10,
    save_period=10,
    verbose=True,
)
print(f"mAP50: {results.results_dict.get('metrics/mAP50(B)', 'N/A')}")
'''


def build_yolo_job_spec(
    frames_dir: str,
    labels_dir: str,
    output_dir: str,
    gpu_type: str = "NVIDIA RTX A5000",
    timeout_minutes: int = 60,
) -> JobSpec:
    """
    Build JobSpec for YOLO nano training.
    Uploads frames + labels.
    Downloads trained model weights.
    """
    return JobSpec(
        job_type="yolo_train",
        gpu_type=gpu_type,
        gpu_count=1,
        upload_paths=[
            frames_dir,
            labels_dir,
        ],
        script=YOLO_SCRIPT,
        download_paths=["/workspace/assets/eic/models/yolo_eic/weights/best.pt"],
        local_output_dir=output_dir,
        timeout_minutes=timeout_minutes,
        pip_packages=["ultralytics"],
    )
