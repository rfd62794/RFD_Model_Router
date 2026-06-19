import time

from mcp.server.fastmcp import FastMCP
from uvicorn import run

from .logger import init_db, log_request
from .router import route

mcp = FastMCP("rfd-model-router", sse_path="/mcp", message_path="/messages/")


@mcp.tool()
async def route_completion(
    task_type: str,
    messages: list[dict],
    system_prompt: str | None = None,
) -> str:
    start = time.perf_counter()
    try:
        text, provider, model, input_tokens, output_tokens = route(
            task_type, messages, system_prompt
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        try:
            log_request(
                task_type, provider, model, input_tokens, output_tokens, duration_ms, True
            )
        except Exception:
            pass
        return text
    except Exception:
        duration_ms = int((time.perf_counter() - start) * 1000)
        try:
            log_request(task_type, "unknown", "unknown", 0, 0, duration_ms, False)
        except Exception:
            pass
        raise


def main() -> None:
    init_db()
    app = mcp.sse_app()
    run(app, host="0.0.0.0", port=8004)


if __name__ == "__main__":
    main()
