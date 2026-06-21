"""Tests for RunpodAdapter."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from rfd_model_router.adapters.runpod_adapter import RunpodAdapter
from rfd_model_router.adapters.compute_base import JobSpec, JobResult


def test_runpod_adapter_requires_api_key():
    """No env var, no arg; verify ValueError raised."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="RUNPOD_API_KEY"):
            RunpodAdapter()


def test_runpod_adapter_accepts_api_key_arg():
    """Pass key as arg; verify no exception."""
    adapter = RunpodAdapter(api_key="test_key")
    assert adapter.api_key == "test_key"


def test_runpod_adapter_accepts_api_key_env():
    """Pass key via env var; verify no exception."""
    with patch.dict("os.environ", {"RUNPOD_API_KEY": "env_key"}):
        adapter = RunpodAdapter()
        assert adapter.api_key == "env_key"


@patch("rfd_model_router.adapters.runpod_adapter.RunpodAdapter._get_client")
def test_run_job_terminates_pod_on_success(mock_get_client):
    """Mock SDK; verify terminate called."""
    mock_client = Mock()
    mock_get_client.return_value = mock_client
    
    mock_client.create_pod.return_value = {"id": "pod-123"}
    mock_client.get_pod.return_value = {"desiredState": "RUNNING"}
    mock_client.execute_pod_command.return_value = {"exitCode": 0}
    mock_client.download_file_from_pod.return_value = None
    
    spec = JobSpec(
        job_type="test",
        gpu_type="NVIDIA RTX A5000",
        gpu_count=1,
        upload_paths=[],
        script="print('test')",
        download_paths=[],
        local_output_dir="/tmp",
        timeout_minutes=10,
        pip_packages=[],
    )
    
    adapter = RunpodAdapter(api_key="test")
    result = adapter.run_job(spec)
    
    mock_client.stop_pod.assert_called_once_with("pod-123")
    assert result.success is True


@patch("rfd_model_router.adapters.runpod_adapter.RunpodAdapter._get_client")
def test_run_job_terminates_pod_on_failure(mock_get_client):
    """Mock SDK upload raises; verify terminate still called."""
    mock_client = Mock()
    mock_get_client.return_value = mock_client
    
    mock_client.create_pod.return_value = {"id": "pod-123"}
    mock_client.get_pod.return_value = {"desiredState": "RUNNING"}
    mock_client.upload_file_to_pod.side_effect = Exception("Upload failed")
    
    spec = JobSpec(
        job_type="test",
        gpu_type="NVIDIA RTX A5000",
        gpu_count=1,
        upload_paths=["/tmp/test.txt"],
        script="print('test')",
        download_paths=[],
        local_output_dir="/tmp",
        timeout_minutes=10,
        pip_packages=[],
    )
    
    adapter = RunpodAdapter(api_key="test")
    result = adapter.run_job(spec)
    
    mock_client.stop_pod.assert_called_once_with("pod-123")
    assert result.success is False
    assert "Upload failed" in result.error


@patch("rfd_model_router.adapters.runpod_adapter.RunpodAdapter._get_client")
def test_run_job_returns_job_result(mock_get_client):
    """Mock full job; verify JobResult returned with success=True."""
    mock_client = Mock()
    mock_get_client.return_value = mock_client
    
    mock_client.create_pod.return_value = {"id": "pod-123"}
    mock_client.get_pod.return_value = {"desiredState": "RUNNING"}
    mock_client.execute_pod_command.return_value = {"exitCode": 0}
    mock_client.download_file_from_pod.return_value = None
    
    spec = JobSpec(
        job_type="test",
        gpu_type="NVIDIA RTX A5000",
        gpu_count=1,
        upload_paths=[],
        script="print('test')",
        download_paths=["/workspace/output.txt"],
        local_output_dir="/tmp",
        timeout_minutes=10,
        pip_packages=[],
    )
    
    adapter = RunpodAdapter(api_key="test")
    result = adapter.run_job(spec)
    
    assert isinstance(result, JobResult)
    assert result.success is True
    assert result.job_type == "test"
    assert result.error is None


@patch("rfd_model_router.adapters.runpod_adapter.RunpodAdapter._get_client")
def test_run_job_failure_returns_result_not_raises(mock_get_client):
    """Mock script fails; verify JobResult.success=False, no exception."""
    mock_client = Mock()
    mock_get_client.return_value = mock_client
    
    mock_client.create_pod.return_value = {"id": "pod-123"}
    mock_client.get_pod.return_value = {"desiredState": "RUNNING"}
    mock_client.execute_pod_command.return_value = {"exitCode": 1}
    
    spec = JobSpec(
        job_type="test",
        gpu_type="NVIDIA RTX A5000",
        gpu_count=1,
        upload_paths=[],
        script="print('test')",
        download_paths=[],
        local_output_dir="/tmp",
        timeout_minutes=10,
        pip_packages=[],
    )
    
    adapter = RunpodAdapter(api_key="test")
    result = adapter.run_job(spec)
    
    assert result.success is False
    assert result.error is not None
    assert "Script execution failed" in result.error


def test_estimate_cost_known_gpu():
    """RTX A5000, 30min timeout; verify cost = 0.27 * 0.5 = 0.135."""
    adapter = RunpodAdapter(api_key="test")
    spec = JobSpec(
        job_type="test",
        gpu_type="NVIDIA RTX A5000",
        gpu_count=1,
        upload_paths=[],
        script="print('test')",
        download_paths=[],
        local_output_dir="/tmp",
        timeout_minutes=30,
        pip_packages=[],
    )
    cost = adapter.estimate_cost(spec)
    assert cost == 0.135  # 0.27 * (30/60)


def test_estimate_cost_unknown_gpu():
    """Unknown GPU type; verify uses default $0.50/hr."""
    adapter = RunpodAdapter(api_key="test")
    spec = JobSpec(
        job_type="test",
        gpu_type="UNKNOWN GPU",
        gpu_count=1,
        upload_paths=[],
        script="print('test')",
        download_paths=[],
        local_output_dir="/tmp",
        timeout_minutes=30,
        pip_packages=[],
    )
    cost = adapter.estimate_cost(spec)
    assert cost == 0.25  # 0.50 * (30/60)


@patch("rfd_model_router.adapters.runpod_adapter.RunpodAdapter._get_client")
def test_wait_for_pod_timeout(mock_get_client):
    """Mock pod never reaches RUNNING; verify returns False."""
    mock_client = Mock()
    mock_get_client.return_value = mock_client
    mock_client.get_pod.return_value = {"desiredState": "PENDING"}
    
    adapter = RunpodAdapter(api_key="test")
    result = adapter._wait_for_pod("pod-123", timeout_seconds=1)
    
    assert result is False
