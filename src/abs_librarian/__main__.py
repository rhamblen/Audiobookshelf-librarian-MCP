"""Entry point: python -m abs_librarian"""

import uvicorn
from .server import cfg, mcp

if __name__ == "__main__":
    app = mcp.streamable_http_app()
    uvicorn.run(app, host="0.0.0.0", port=cfg.port)
