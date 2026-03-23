# src/main.py
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="MBSE Model Generator")
    parser.add_argument("--web", action="store_true", help="Start web interface")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--setup", action="store_true", help="Interactive setup wizard")
    args = parser.parse_args()

    if args.setup:
        _run_setup()
    elif args.web:
        _start_web(args.host, args.port)
    else:
        parser.print_help()


def _start_web(host: str, port: int):
    import uvicorn
    from src.web.app import app
    print(f"\n  MBSE Model Generator")
    print(f"  http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _run_setup():
    """Interactive setup: prompt for API keys and write .env file."""
    from pathlib import Path
    from src.config import PACKAGE_ROOT
    env_path = PACKAGE_ROOT / ".env"
    print("\n  MBSE Generator Setup\n")
    provider = input("  Provider (anthropic/openrouter/local) [openrouter]: ").strip() or "openrouter"
    lines = [f"PROVIDER={provider}"]
    if provider in ("anthropic", "openrouter"):
        key_name = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENROUTER_API_KEY"
        key = input(f"  {key_name}: ").strip()
        lines.append(f"{key_name}={key}")
    if provider == "local":
        url = input("  LOCAL_LLM_URL [http://localhost:11434/v1]: ").strip() or "http://localhost:11434/v1"
        lines.append(f"LOCAL_LLM_URL={url}")
    model = input("  MODEL [anthropic/claude-sonnet-4]: ").strip() or "anthropic/claude-sonnet-4"
    lines.append(f"MODEL={model}")
    mode = input("  DEFAULT_MODE (capella/rhapsody) [capella]: ").strip() or "capella"
    lines.append(f"DEFAULT_MODE={mode}")
    env_path.write_text("\n".join(lines) + "\n")
    print(f"\n  Config saved to {env_path}\n")


if __name__ == "__main__":
    main()
