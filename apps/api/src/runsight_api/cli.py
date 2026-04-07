"""CLI entry point for `uvx runsight` / `runsight` command."""

import sys

import uvicorn


def main() -> None:
    # Parse --host and --port from argv (keep it minimal)
    host = "0.0.0.0"
    port = 8000

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        elif args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif args[i] in ("--help", "-h"):
            print("Usage: runsight [--host HOST] [--port PORT]")
            print()
            print("Start the Runsight server.")
            print()
            print("Options:")
            print("  --host HOST  Bind address (default: 0.0.0.0)")
            print("  --port PORT  Bind port (default: 8000)")
            sys.exit(0)
        else:
            print(f"Unknown argument: {args[i]}", file=sys.stderr)
            sys.exit(1)

    print(f"  Runsight running at http://localhost:{port}")
    print("  Press Ctrl+C to stop")
    print()

    uvicorn.run("runsight_api.main:app", host=host, port=port)
