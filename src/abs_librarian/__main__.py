"""Entry point: python -m abs_librarian"""

import uvicorn
from starlette.responses import JSONResponse

from .server import cfg, mcp

# Use FastMCP's own ASGI app so its lifespan (task group) initialises correctly.
# A thin wrapper intercepts /health before passing through to the MCP handler.
_mcp_app = mcp.streamable_http_app()


async def app(scope, receive, send):
    if scope["type"] == "http" and scope.get("path") == "/health":
        response = JSONResponse({"status": "ok", "version": "0.1.0"})
        await response(scope, receive, send)
    else:
        await _mcp_app(scope, receive, send)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=cfg.port)
