import json
import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from starlette.responses import JSONResponse

from .logger import DB_PATH, init_db, log_request
from .models import RouteRequest, RouteResponse
from .router import load_config, route, route_stream

load_dotenv()

REQUIRED_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def rotate_old_logs() -> None:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "DELETE FROM requests WHERE timestamp < datetime('now', '-30 days')"
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    for provider, key in REQUIRED_KEYS.items():
        if not os.getenv(key):
            logging.warning(f"Missing API key for provider '{provider}': {key} not set")
    rotate_old_logs()
    init_db()
    yield


app = FastAPI(title="RFD Model Router API", lifespan=lifespan)


@app.post("/route", response_model=RouteResponse)
async def route_completion(request: RouteRequest):
    start = time.perf_counter()
    try:
        messages = [msg.model_dump() for msg in request.messages]
        text, provider, model, input_tokens, output_tokens = route(
            task_type=request.task_type,
            messages=messages,
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


@app.post("/route/stream")
def route_stream_endpoint(request: RouteRequest):
    def generate():
        gen = route_stream(
            request.task_type,
            [m.model_dump() for m in request.messages],
            request.system_prompt,
        )
        try:
            while True:
                chunk = next(gen)
                yield f"data: {json.dumps({'token': chunk, 'done': False})}\n\n"
        except StopIteration as e:
            meta = e.value or {}
            yield f"data: {json.dumps({**meta, 'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


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
        "total_cost_usd": 0.0,
        "by_task_type": {},
        "by_provider": {},
    }
    try:
        if not DB_PATH.exists():
            return totals
        config = load_config()
        budgets = config.get("budgets", {})
        today = time.strftime("%Y-%m-%d", time.gmtime())
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT task_type, provider,
                    COUNT(*) AS requests,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(cost_usd), 0.0) AS cost_usd
                FROM requests
                GROUP BY task_type, provider
                """
            ).fetchall()
            # Get daily spend per provider
            daily_spend_rows = conn.execute(
                """
                SELECT provider, COALESCE(SUM(cost_usd), 0.0) AS daily_spend
                FROM requests
                WHERE timestamp LIKE ?
                GROUP BY provider
                """,
                (f"{today}%",),
            ).fetchall()
        daily_spend_map = {row["provider"]: row["daily_spend"] for row in daily_spend_rows}
        for row in rows:
            task_type = row["task_type"]
            provider = row["provider"]
            requests = row["requests"]
            input_tokens = row["input_tokens"]
            output_tokens = row["output_tokens"]
            cost_usd = row["cost_usd"]
            totals["total_requests"] += requests
            totals["total_input_tokens"] += input_tokens
            totals["total_output_tokens"] += output_tokens
            totals["total_cost_usd"] += cost_usd
            totals["by_task_type"].setdefault(
                task_type, {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            )
            group = totals["by_task_type"][task_type]
            group["requests"] += requests
            group["input_tokens"] += input_tokens
            group["output_tokens"] += output_tokens
            group["cost_usd"] += cost_usd
            totals["by_provider"].setdefault(
                provider,
                {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                    "daily_limit_usd": 0.0,
                    "daily_spend_usd": 0.0,
                },
            )
            group = totals["by_provider"][provider]
            group["requests"] += requests
            group["input_tokens"] += input_tokens
            group["output_tokens"] += output_tokens
            group["cost_usd"] += cost_usd
            group["daily_limit_usd"] = budgets.get(provider, {}).get("daily_limit_usd", 0.0)
            group["daily_spend_usd"] = daily_spend_map.get(provider, 0.0)
    except Exception:
        log_request("usage", "unknown", "unknown", 0, 0, 0, False)
    return totals


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=500)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8005)


if __name__ == "__main__":
    main()
