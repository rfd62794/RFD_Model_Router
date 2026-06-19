import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.responses import JSONResponse

from .logger import init_db, log_request
from .router import route

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
