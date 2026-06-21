# RFD_Model_Router - Current State

## Phase
Phase 7: RunPod Compute Adapter — **Complete**

## Floor
113 passing, 0 failing, 0 skipped

## Date
June 2026

## Completed Work

### Phase 7 (RunPod Compute Adapter)
- `rfd_model_router/adapters/compute_base.py` — ComputeAdapter ABC with `run_job()` interface
- `rfd_model_router/adapters/runpod_adapter.py` — RunPod SDK wrapper for GPU compute jobs
- `rfd_model_router/jobs/__init__.py` — Jobs package init
- `rfd_model_router/jobs/owl_job.py` — OWLv2 labeling job definition
- `rfd_model_router/jobs/yolo_job.py` — YOLO nano training job definition
- `rfd_model_router/adapters/__init__.py` — Export RunpodAdapter and compute base classes
- `tests/test_runpod_adapter.py` — 10 tests for RunpodAdapter (SDK mocked)
- `tests/test_compute_jobs.py` — 10 tests for OWL and YOLO job specs
- `runpod>=1.0.0` added to pyproject.toml dependencies
- ADR-006 documented at `docs/adr/ADR-006.md`

### Previous Phases
- Phase 1-6: Anthropic, Groq, Gemini, OpenRouter adapters, MCP server, REST API

## Architecture Decisions

### ADR-006: RunPod as Parallel Compute Provider
- ComputeAdapter hierarchy parallel to BaseAdapter (language inference)
- ComputeAdapter exposes `run_job()` instead of `complete()`/`stream()`
- RunpodAdapter implements ComputeAdapter using runpod SDK
- Job definitions in `rfd_model_router/jobs/` — one file per job type
- Lazy import pattern for runpod SDK (inside `_get_client()`)
- Pod always terminated in finally block — never left running
- RUNPOD_API_KEY required in environment

## Next Phase
Phase 4 of RFD_CLIPr: Wire RunpodAdapter into CLIPr pipeline for OWLv2 + YOLO job triggering
