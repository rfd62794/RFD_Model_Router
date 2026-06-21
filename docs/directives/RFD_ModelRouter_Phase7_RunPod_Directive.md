# RFD_Model_Router — Phase 7 Directive: RunPod Compute Adapter

*June 2026 | Read fully before executing anything.*

---

> ⛔ **STOP:** Run pytest before touching any file.
> Must report **93 passing, 0 failing, 0 skipped**.
> If count differs, stop and report — do not proceed.

---

## §0 Context

**What exists:**
- RFD_Model_Router at 93/0/0 — Anthropic, Groq, Gemini, OpenRouter adapters live
- All adapters extend `BaseAdapter` with `complete()` and `stream()` interface
- REST API at :8005, MCP server at :8004
- NSSM services running on Nitro 5

**What Phase 7 delivers:**
A `RunpodAdapter` that treats RunPod as a compute provider — not a language model. It handles GPU job execution: spinning up pods, uploading data, running scripts, downloading results, terminating pods. This enables RFD_CLIPr to trigger OWLv2 labeling passes and YOLO training runs programmatically without SSH or manual intervention.

**Architecture note:**
RunPod is NOT a language model adapter. It does not implement `complete()` or `stream()`. It implements a separate `ComputeAdapter` base class with `run_job()`. The two adapter hierarchies are parallel — they share the router infrastructure but serve different purposes:

```
BaseAdapter (language inference)
  → AnthropicAdapter
  → GroqAdapter
  → GeminiAdapter
  → OpenRouterAdapter

ComputeAdapter (GPU compute jobs)
  → RunpodAdapter   ← this phase
```

**What is NOT in scope:**
- Wiring RunpodAdapter into CLIPr (CLIPr Phase 4)
- Serverless RunPod endpoints (pods only, this phase)
- Multi-GPU jobs
- Any changes to existing adapters, API routes, or MCP tools
- NSSM service restart (adapter is imported, not a separate service)

---

## §1 Scope Statement

| File | Status | Action |
|---|---|---|
| `rfd_model_router/adapters/compute_base.py` | New | ComputeAdapter ABC — `run_job()` interface |
| `rfd_model_router/adapters/runpod_adapter.py` | New | RunPod SDK wrapper — pod lifecycle + job execution |
| `rfd_model_router/jobs/__init__.py` | New | Jobs package init |
| `rfd_model_router/jobs/owl_job.py` | New | OWLv2 labeling job definition |
| `rfd_model_router/jobs/yolo_job.py` | New | YOLO nano training job definition |
| `rfd_model_router/adapters/__init__.py` | Modify | Export RunpodAdapter |
| `tests/test_runpod_adapter.py` | New | RunpodAdapter tests (SDK mocked) |
| `tests/test_compute_jobs.py` | New | OWL + YOLO job tests |
| `docs/adr/ADR-006.md` | New | RunPod as parallel compute provider |
| `docs/state/current.md` | Modify | Update to Phase 7 |

**Read-only — do not touch:**
`rfd_model_router/adapters/base.py`,
`rfd_model_router/adapters/anthropic_adapter.py`,
`rfd_model_router/adapters/groq_adapter.py`,
`rfd_model_router/adapters/gemini_adapter.py`,
`rfd_model_router/adapters/openrouter_adapter.py`,
`rfd_model_router/api.py`,
all existing tests

---

## §2 Implementation

### 2.1 `docs/adr/ADR-006.md`

Write before any code.

```markdown
# ADR-006: RunPod as Parallel Compute Provider

## Status
Accepted

## Context
RFD_Model_Router routes language inference requests to cloud API providers.
GPU-heavy batch jobs (OWLv2 labeling, YOLO training, BLIP-2 enrichment)
cannot run on Nitro (4GB VRAM ceiling) and require on-demand GPU compute.
RunPod provides per-second billed GPU pods via a Python SDK.

## Decision
Add a parallel ComputeAdapter hierarchy alongside the existing BaseAdapter
hierarchy. ComputeAdapter exposes run_job() rather than complete()/stream().
RunpodAdapter implements ComputeAdapter using the runpod SDK.

Job definitions live in rfd_model_router/jobs/ — one file per job type.
Each job knows its GPU requirements, data transfer spec, and execution script.
RunpodAdapter is responsible only for pod lifecycle — not job logic.

## Consequences
- GPU compute jobs are programmable, not manual
- CLIPr can trigger OWLv2 + YOLO runs without SSH
- Adding new job types = new file in jobs/, no changes to adapter
- runpod SDK must be added to pyproject.toml dependencies
- RUNPOD_API_KEY required in environment
```

---

### 2.2 `rfd_model_router/adapters/compute_base.py`

```python
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
```

> ⚠️ RULE: `JobSpec` and `JobResult` are dataclasses — not Pydantic models. No external dependencies in compute_base.py. Pure stdlib only.

---

### 2.3 `rfd_model_router/adapters/runpod_adapter.py`

```python
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


class RunpodAdapter(ComputeAdapter):
    def __init__(self, api_key: str | None = None):
        """
        Initialize RunPod adapter.
        api_key defaults to RUNPOD_API_KEY env var.
        """

    def _get_client(self):
        """Return configured runpod module. Lazy import."""

    def _wait_for_pod(self, pod_id: str, timeout_seconds: int = 120) -> bool:
        """
        Poll pod status until RUNNING or timeout.
        Returns True if pod reached RUNNING state.
        """

    def _install_packages(self, pod_id: str, packages: list[str]) -> bool:
        """Run pip install on pod. Returns True on success."""

    def _upload_paths(self, pod_id: str, local_paths: list[str]) -> bool:
        """
        Upload local files/directories to pod /workspace/.
        Returns True on success.
        """

    def _run_script(self, pod_id: str, script: str, timeout_minutes: int) -> bool:
        """
        Write script to pod and execute it.
        Returns True if script exits 0.
        """

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

    def _terminate_pod(self, pod_id: str) -> None:
        """Terminate pod. Always called — even on failure."""

    def run_job(self, spec: JobSpec) -> JobResult:
        """
        Execute GPU compute job end-to-end.
        Pod is always terminated in finally block — never left running.
        """

    def estimate_cost(self, spec: JobSpec) -> float:
        """Estimate cost: hourly_rate * (timeout_minutes / 60)."""
```

> ⚠️ RULE: `import runpod` is a lazy import inside `_get_client()` — never at module level. This allows the module to import cleanly without the SDK installed, and allows tests to mock it without patching sys.modules at import time.

> ⚠️ RULE: `_terminate_pod()` is ALWAYS called in a `finally` block inside `run_job()`. A pod that fails mid-job must still be terminated. Never let billing run on a failed pod.

> ⚠️ RULE: `RUNPOD_API_KEY` is read from environment via `os.environ.get("RUNPOD_API_KEY")`. Never hardcode. If missing, raise `ValueError` with a clear message at `__init__` time.

> ⚠️ RULE: `GPU_RATES` dict is for cost estimation only — not for pod selection. The actual GPU requested is `spec.gpu_type`. If `spec.gpu_type` not in `GPU_RATES`, use a default rate of $0.50/hr for estimation.

> ⚠️ RULE: All RunPod SDK calls wrapped in try/except. Failures set `JobResult.success=False` and `error` field. Never raise from `run_job()` — always return a `JobResult`.

---

### 2.4 `rfd_model_router/jobs/owl_job.py`

Job definition for OWLv2 auto-labeling pass. Knows what to upload, what script to run, what to download.

```python
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
```

> ⚠️ RULE: `OWL_SCRIPT` is a module-level string constant. Never build it dynamically inside the function. The script is a fixed artifact — changes to it require editing this file explicitly.

---

### 2.5 `rfd_model_router/jobs/yolo_job.py`

```python
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
print(f"mAP50: {results.results_dict.get(\'metrics/mAP50(B)\', \'N/A\')}")
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
```

> ⚠️ RULE: `YOLO_SCRIPT` hardcodes 13 EIC classes. When adding a new game, a new job file is created — not a modified version of this one. Per-game job files, not parameterized scripts.

---

## §3 Test Anchors

### `tests/test_runpod_adapter.py`

| Test | Behaviour |
|---|---|
| `test_runpod_adapter_requires_api_key` | No env var, no arg; verify ValueError raised |
| `test_runpod_adapter_accepts_api_key_arg` | Pass key as arg; verify no exception |
| `test_run_job_terminates_pod_on_success` | Mock SDK; verify terminate called |
| `test_run_job_terminates_pod_on_failure` | Mock SDK upload raises; verify terminate still called |
| `test_run_job_returns_job_result` | Mock full job; verify JobResult returned with success=True |
| `test_run_job_failure_returns_result_not_raises` | Mock script fails; verify JobResult.success=False, no exception |
| `test_estimate_cost_known_gpu` | RTX A5000, 30min timeout; verify cost = 0.27 * 0.5 = 0.135 |
| `test_estimate_cost_unknown_gpu` | Unknown GPU type; verify uses default $0.50/hr |
| `test_wait_for_pod_timeout` | Mock pod never reaches RUNNING; verify returns False |

### `tests/test_compute_jobs.py`

| Test | Behaviour |
|---|---|
| `test_owl_job_spec_has_correct_type` | build_owl_job_spec(); verify job_type == "owl_label" |
| `test_owl_job_spec_upload_paths_count` | verify 4 upload paths |
| `test_owl_job_spec_download_path` | verify download_paths contains "labels" |
| `test_yolo_job_spec_has_correct_type` | build_yolo_job_spec(); verify job_type == "yolo_train" |
| `test_yolo_job_spec_upload_paths_count` | verify 2 upload paths |
| `test_yolo_job_spec_download_path` | verify download_paths contains "best.pt" |

> ⚠️ RULE: `import runpod` never happens in tests. Mock at `rfd_model_router.adapters.runpod_adapter` module boundary using `unittest.mock.patch`. The lazy import pattern in `_get_client()` makes this straightforward.

> ⚠️ RULE: No real RunPod API calls in tests. No real file uploads. All SDK interactions mocked.

**Target: 108 passing, 0 failing, 0 skipped** (93 existing + 15 new)

---

## §4 Completion Criteria

- [ ] pytest: **108 passing, 0 failing, 0 skipped** — raw terminal output pasted
- [ ] `uv add runpod` added to pyproject.toml and installed
- [ ] `RunpodAdapter` importable: `from rfd_model_router.adapters.runpod_adapter import RunpodAdapter`
- [ ] `build_owl_job_spec` importable: `from rfd_model_router.jobs.owl_job import build_owl_job_spec`
- [ ] `build_yolo_job_spec` importable: `from rfd_model_router.jobs.yolo_job import build_yolo_job_spec`
- [ ] Manual smoke (dry run — no real pod): `uv run python -c "from rfd_model_router.adapters.runpod_adapter import RunpodAdapter; a = RunpodAdapter(api_key='test'); print(a.estimate_cost.__doc__)"`
- [ ] ADR-006 written to `docs/adr/ADR-006.md`
- [ ] `docs/state/current.md` updated: Phase 7, floor 108/0/0, next = CLIPr Phase 4 (wire RunpodAdapter into CLIPr pipeline)
- [ ] NSSM service restart NOT required — adapter is imported, not a separate service

---

## §5 Quick Reference

| Key | Value |
|---|---|
| Baseline floor | 93/0/0 |
| Target floor | 108/0/0 |
| New package | `runpod` (add via `uv add runpod`) |
| New env var | `RUNPOD_API_KEY` |
| Adapter hierarchy | ComputeAdapter (parallel to BaseAdapter) |
| runpod import | Lazy — inside `_get_client()` only |
| terminate_pod | Always in finally block — non-negotiable |
| GPU default | NVIDIA RTX A5000, $0.27/hr |
| Job types | owl_label, yolo_train |
| Per-game jobs | One file per game in jobs/ — never parameterize |
| NSSM restart | Not required |
| CLIPr wiring | Phase 4 of CLIPr — not this directive |
| runpod in tests | Always mocked — never real SDK calls |
