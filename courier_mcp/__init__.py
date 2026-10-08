"""Read-only Courier MCP server (Streamable HTTP, JSON responses).

Exposes mission status and receipts from one configured state directory, or
bundled synthetic demo data. It has no write tools and runs no commands.
Real mode reads the bridge state and the controller journal through
``courier_core.receipt_read_model`` and no other paths.
"""

__version__ = "0.1.0"
