import os
import sqlite3
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.responses import JSONResponse

from .logger import DB_PATH, init_db, log_request
from .router import load_config, route

load_dotenv()


class RouteRequest(BaseModel):
    task_type: str
    messages: list[dict]
    system_prompt: str | None = None


class RouteResponse(BaseModel):
    completion: str
    provider: str
    model: str
    tokens: dict


app = FastAPI(title="RFD Model Router API")


@app.post("/route", response_model=RouteResponse)
async def route_completion(request: RouteRequest):
    start = time.perf_counter()
    try:
        text, provider, model, input_tokens, output_tokens = route(
            task_type=request.task_type,
            messages=request.messages,
            system_prompt=request.system_prompt,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        try:
            log_request(
                request.task_type, provider, model, input_tokens, output_tokens, duration_ms, True
            )
        except Exception:
            pass
        return {
            "completion": text,
            "provider": provider,
            "model": model,
            "tokens": {"input": input_tokens, "output": output_tokens},
        }
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        try:
            log_request(request.task_type, "unknown", "unknown", 0, 0, duration_ms, False)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "providers": ["anthropic", "groq", "gemini", "openrouter"],
        "config_loaded": bool(load_config()),
    }


@app.get("/usage")
def usage():
    totals = {
        "total_requests": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "by_task_type": {},
        "by_provider": {},
    }
    try:
        if not DB_PATH.exists():
            return totals
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT task_type, provider,
                    COUNT(*) AS requests,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens
                FROM requests
                GROUP BY task_type, provider
                """
            ).fetchall()
        for row in rows:
            task_type = row["task_type"]
            provider = row["provider"]
            requests = row["requests"]
            input_tokens = row["input_tokens"]
            output_tokens = row["output_tokens"]
            totals["total_requests"] += requests
            totals["total_input_tokens"] += input_tokens
            totals["total_output_tokens"] += output_tokens
            totals["by_task_type"].setdefault(
                task_type, {"requests": 0, "input_tokens": 0, "output_tokens": 0}
            )
            group = totals["by_task_type"][task_type]
            group["requests"] += requests
            group["input_tokens"] += input_tokens
            group["output_tokens"] += output_tokens
            totals["by_provider"].setdefault(
                provider, {"requests": 0, "input_tokens": 0, "output_tokens": 0}
            )
            group = totals["by_provider"][provider]
            group["requests"] += requests
            group["input_tokens"] += input_tokens
            group["output_tokens"] += output_tokens
    except Exception as exc:
        log_request("usage", "unknown", "unknown", 0, 0, 0, False)
    return totals


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=500)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app.router.lifespan_context = lifespan


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8005)


if __name__ == "__main__":
    main()
