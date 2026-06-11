"""Entry point: python -m abs_librarian"""

from .server import cfg, mcp

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=cfg.port)
