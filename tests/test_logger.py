import sqlite3
from unittest.mock import patch

from rfd_model_router import logger


def test_init_db_creates_table(tmp_path):
    with patch.object(logger, "DB_PATH", tmp_path / "test.db"):
        logger.init_db()
        with sqlite3.connect(tmp_path / "test.db") as conn:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='requests'"
            )
            assert cur.fetchone() is not None


def test_logger_writes_row(tmp_path):
    with patch.object(logger, "DB_PATH", tmp_path / "test.db"):
        logger.init_db()
        logger.log_request("code", "groq", "llama", 10, 5, 100, True)
        with sqlite3.connect(tmp_path / "test.db") as conn:
            rows = conn.execute("SELECT * FROM requests").fetchall()
            assert len(rows) == 1
            assert rows[0][2] == "code"


def test_log_request_marks_success(tmp_path):
    with patch.object(logger, "DB_PATH", tmp_path / "test.db"):
        logger.init_db()
        logger.log_request("code", "groq", "llama", 1, 1, 1, True)
        with sqlite3.connect(tmp_path / "test.db") as conn:
            row = conn.execute("SELECT success FROM requests").fetchone()
            assert row[0] == 1


def test_log_request_marks_failure(tmp_path):
    with patch.object(logger, "DB_PATH", tmp_path / "test.db"):
        logger.init_db()
        logger.log_request("code", "groq", "llama", 1, 1, 1, False)
        with sqlite3.connect(tmp_path / "test.db") as conn:
            row = conn.execute("SELECT success FROM requests").fetchone()
            assert row[0] == 0


def test_logger_failure_is_silent(tmp_path):
    with patch.object(logger, "DB_PATH", tmp_path / "test.db"):
        (tmp_path / "test.db").mkdir()
        logger.log_request("code", "groq", "llama", 10, 5, 100, True)


def test_log_request_failure_logs_warning(tmp_path, caplog):
    with patch.object(logger, "DB_PATH", tmp_path / "test.db"):
        (tmp_path / "test.db").mkdir()
        with caplog.at_level("WARNING", logger="rfd_model_router.logger"):
            logger.log_request("code", "groq", "llama", 10, 5, 100, True)
    assert any("log_request failed" in r.message for r in caplog.records)


def test_api_main_binds_localhost_by_default():
    import os
    from rfd_model_router import api
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("RFD_MODEL_ROUTER_HOST", None)
        with patch("uvicorn.run") as mock_run:
            api.main()
    assert mock_run.call_args.kwargs["host"] == "127.0.0.1"
