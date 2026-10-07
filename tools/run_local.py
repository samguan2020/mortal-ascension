"""Run the real-provider API on loopback for the Vite development client."""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

from dotenv import dotenv_values
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloud.server import Settings, create_app

DEFAULT_CONFIG = ROOT / "backend" / ".env"


def load_local_settings(config_path: Path, frontend_port: int) -> Settings:
    """Load only the provider values needed by the loopback runtime."""
    values = dotenv_values(config_path)
    required = ("LLM_API_KEY", "LLM_MODEL_ID", "LLM_BASE_URL")
    missing = [name for name in required if not values.get(name)]
    if missing:
        raise RuntimeError(f"Missing local provider configuration: {', '.join(missing)}")
    settings = Settings(
        site_password=secrets.token_urlsafe(48),
        public_origin=f"http://127.0.0.1:{frontend_port}",
        llm_model_id=str(values["LLM_MODEL_ID"]),
        llm_base_url=str(values["LLM_BASE_URL"]),
        llm_api_key=str(values["LLM_API_KEY"]),
        static_dir=None,
        local_development=True,
    )
    settings.validate()
    return settings


def parse_args() -> argparse.Namespace:
    """Parse loopback server options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000, help="Loopback API port (default: 8000)")
    parser.add_argument(
        "--frontend-port", type=int, default=5174,
        help="Exact Vite origin port allowed to send chat requests (default: 5174)",
    )
    parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG,
        help="Private dotenv file containing the three LLM provider values",
    )
    return parser.parse_args()


def main() -> None:
    """Start one non-reloading local API worker."""
    args = parse_args()
    for name, value in (("port", args.port), ("frontend port", args.frontend_port)):
        if not 1 <= value <= 65535:
            raise SystemExit(f"{name} must be between 1 and 65535")
    try:
        settings = load_local_settings(args.config, args.frontend_port)
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
    uvicorn.run(
        create_app(settings), host="127.0.0.1", port=args.port,
        workers=1, access_log=False,
    )


if __name__ == "__main__":
    main()
