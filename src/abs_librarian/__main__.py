"""Entry point: python -m abs_librarian"""

import json
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .server import cfg, mcp


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "version": "0.1.0"})


app = Starlette(routes=[
    Route("/health", health),
    Mount("/", app=mcp.streamable_http_app()),
])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=cfg.port)
