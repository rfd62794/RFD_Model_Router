"""Tests for compute job specifications."""
from rfd_model_router.jobs.owl_job import build_owl_job_spec
from rfd_model_router.jobs.yolo_job import build_yolo_job_spec
from rfd_model_router.adapters.compute_base import JobSpec


def test_owl_job_spec_has_correct_type():
    """build_owl_job_spec(); verify job_type == "owl_label"."""
    spec = build_owl_job_spec(
        frames_dir="/tmp/frames",
        processed_dir="/tmp/processed",
        preset_path="/tmp/preset.yaml",
        owl_py_path="/tmp/owl.py",
        output_dir="/tmp/output",
    )
    assert spec.job_type == "owl_label"


def test_owl_job_spec_upload_paths_count():
    """verify 4 upload paths."""
    spec = build_owl_job_spec(
        frames_dir="/tmp/frames",
        processed_dir="/tmp/processed",
        preset_path="/tmp/preset.yaml",
        owl_py_path="/tmp/owl.py",
        output_dir="/tmp/output",
    )
    assert len(spec.upload_paths) == 4


def test_owl_job_spec_download_path():
    """verify download_paths contains "labels"."""
    spec = build_owl_job_spec(
        frames_dir="/tmp/frames",
        processed_dir="/tmp/processed",
        preset_path="/tmp/preset.yaml",
        owl_py_path="/tmp/owl.py",
        output_dir="/tmp/output",
    )
    assert "/workspace/assets/eic/labels" in spec.download_paths


def test_owl_job_spec_default_gpu():
    """verify default GPU is RTX A5000."""
    spec = build_owl_job_spec(
        frames_dir="/tmp/frames",
        processed_dir="/tmp/processed",
        preset_path="/tmp/preset.yaml",
        owl_py_path="/tmp/owl.py",
        output_dir="/tmp/output",
    )
    assert spec.gpu_type == "NVIDIA RTX A5000"


def test_owl_job_spec_custom_gpu():
    """verify custom GPU type is respected."""
    spec = build_owl_job_spec(
        frames_dir="/tmp/frames",
        processed_dir="/tmp/processed",
        preset_path="/tmp/preset.yaml",
        owl_py_path="/tmp/owl.py",
        output_dir="/tmp/output",
        gpu_type="NVIDIA RTX 4090",
    )
    assert spec.gpu_type == "NVIDIA RTX 4090"


def test_yolo_job_spec_has_correct_type():
    """build_yolo_job_spec(); verify job_type == "yolo_train"."""
    spec = build_yolo_job_spec(
        frames_dir="/tmp/frames",
        labels_dir="/tmp/labels",
        output_dir="/tmp/output",
    )
    assert spec.job_type == "yolo_train"


def test_yolo_job_spec_upload_paths_count():
    """verify 2 upload paths."""
    spec = build_yolo_job_spec(
        frames_dir="/tmp/frames",
        labels_dir="/tmp/labels",
        output_dir="/tmp/output",
    )
    assert len(spec.upload_paths) == 2


def test_yolo_job_spec_download_path():
    """verify download_paths contains "best.pt"."""
    spec = build_yolo_job_spec(
        frames_dir="/tmp/frames",
        labels_dir="/tmp/labels",
        output_dir="/tmp/output",
    )
    assert "/workspace/assets/eic/models/yolo_eic/weights/best.pt" in spec.download_paths


def test_yolo_job_spec_default_gpu():
    """verify default GPU is RTX A5000."""
    spec = build_yolo_job_spec(
        frames_dir="/tmp/frames",
        labels_dir="/tmp/labels",
        output_dir="/tmp/output",
    )
    assert spec.gpu_type == "NVIDIA RTX A5000"


def test_yolo_job_spec_custom_gpu():
    """verify custom GPU type is respected."""
    spec = build_yolo_job_spec(
        frames_dir="/tmp/frames",
        labels_dir="/tmp/labels",
        output_dir="/tmp/output",
        gpu_type="NVIDIA RTX 3090",
    )
    assert spec.gpu_type == "NVIDIA RTX 3090"
