"""Generate an editable GLB motion source without exposing credentials."""

from __future__ import annotations

import argparse
import base64
import http.cookiejar
import json
import os
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_SOURCE_ROOT = PROJECT_ROOT / "assets" / "source"
DEFAULT_OUTPUT = ASSET_SOURCE_ROOT / "motions" / "liu_talk_source.glb"


class SayMotionError(RuntimeError):
    """Raised when SayMotion returns an invalid or unsuccessful response."""


class SayMotionClient:
    """Minimal server-side-style client for the SayMotion REST API."""

    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        if not client_id or not client_secret:
            raise ValueError("SAYMOTION_CLIENT_ID and SAYMOTION_CLIENT_SECRET are required")
        if not base_url.startswith("https://"):
            raise ValueError("SAYMOTION_API_URL must use HTTPS")

        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )

    def authenticate(self) -> None:
        encoded = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).decode("ascii")
        self._request_json(
            "/account/v1/auth",
            headers={"Authorization": f"Basic {encoded}"},
        )
        if not any(cookie.name == "dmsess" for cookie in self.cookie_jar):
            raise SayMotionError("Authentication succeeded without a dmsess cookie")

    def list_models(self) -> list[dict[str, Any]]:
        payload = self._request_json("/character/v1/listModels?stockModel=all")
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("list"), list):
            return payload["list"]
        raise SayMotionError("Unexpected character model response")

    def get_credit_balance(self) -> dict[str, Any]:
        payload = self._request_json("/account/v1/creditBalance")
        if not isinstance(payload, dict):
            raise SayMotionError("Unexpected credit balance response")
        return payload

    def submit(self, prompt: str, model_id: str, duration: float | None) -> str:
        params = [
            f"prompt={json.dumps(prompt, ensure_ascii=False)}",
            f"model={model_id}",
            "numVariant=1",
        ]
        if duration is not None:
            params.append(f"requestedAnimationDuration={duration:g}")
        payload = self._request_json(
            "/job/v1/process/text2motion",
            method="POST",
            body={"params": params},
        )
        rid = payload.get("rid") if isinstance(payload, dict) else None
        if not isinstance(rid, str) or not rid:
            raise SayMotionError("Job response did not contain a request id")
        return rid

    def wait_for_job(self, rid: str, timeout_seconds: float = 120.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_status = "UNKNOWN"
        while time.monotonic() < deadline:
            payload = self._request_json(f"/job/v1/status/{rid}")
            last_status = extract_job_status(payload)
            print(f"SayMotion status: {last_status}")
            if last_status == "SUCCESS":
                return
            if last_status == "FAILURE":
                detail = json.dumps(payload, ensure_ascii=False)
                raise SayMotionError(f"SayMotion job {rid} failed: {detail}")
            time.sleep(2.0)
        raise SayMotionError(
            f"SayMotion job {rid} timed out after {timeout_seconds:g}s "
            f"(last status: {last_status})"
        )

    def get_glb_url(self, rid: str) -> str:
        payload = self._request_json(f"/job/v1/download/{rid}?variant_id=1")
        return extract_glb_url(payload)

    def download(self, url: str, destination: Path) -> None:
        if not url.startswith("https://"):
            raise SayMotionError("SayMotion returned a non-HTTPS download URL")
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, method="GET")
        try:
            with self.opener.open(request, timeout=90) as response:
                destination.write_bytes(response.read())
        except (urllib.error.HTTPError, urllib.error.URLError) as error:
            raise SayMotionError(f"GLB download failed: {error}") from error

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        request_headers = {"Accept": "application/json", **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=45) as response:
                content = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise SayMotionError(f"SayMotion HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            raise SayMotionError(f"SayMotion request failed: {error}") from error

        if not content:
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError as error:
            raise SayMotionError("SayMotion returned invalid JSON") from error


def extract_job_status(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise SayMotionError("Unexpected job status response")
    statuses = payload.get("status")
    if not isinstance(statuses, list) or not statuses:
        raise SayMotionError("Job status response did not contain statuses")
    status = statuses[0].get("status")
    if not isinstance(status, str) or not status:
        raise SayMotionError("Job status entry did not contain a status")
    return status.upper()


def extract_glb_url(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise SayMotionError("Unexpected download response")
    for link in payload.get("links", []):
        for url_entry in link.get("urls", []):
            for file_entry in url_entry.get("files", []):
                glb_url = file_entry.get("glb")
                if isinstance(glb_url, str) and glb_url:
                    return glb_url
    raise SayMotionError("SayMotion download response did not contain a GLB")


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def select_model(models: list[dict[str, Any]], requested_id: str | None) -> str:
    if not models:
        raise SayMotionError("No character models are available on this account")
    if requested_id:
        for model in models:
            model_id = str(model.get("id", model.get("Id", "")))
            if model_id == requested_id:
                return model_id
        raise SayMotionError(f"Character model {requested_id!r} was not found")
    model_id = str(models[0].get("id", models[0].get("Id", "")))
    if not model_id:
        raise SayMotionError("The first character model did not contain an id")
    return model_id


def require_available_credits(balance: dict[str, Any]) -> float:
    credits = balance.get("credits")
    if not isinstance(credits, (int, float)):
        raise SayMotionError("Credit balance response did not contain a numeric balance")
    if credits <= 0:
        plan = balance.get("subscription", {}).get("name", "unknown")
        raise SayMotionError(
            f"SayMotion account has 0 available API credits (plan: {plan}). "
            "Activate or add API credits before generating."
        )
    return float(credits)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a SayMotion GLB for the Tingyu Inn prototype."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default=(
            "A calm middle-aged innkeeper stands naturally, breathes subtly, "
            "and makes restrained hand gestures in a seamless idle loop."
        ),
    )
    parser.add_argument("--model-id", help="SayMotion character model id; defaults to the first")
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="Authenticate and print available character model ids without generating",
    )
    parser.add_argument(
        "--credits",
        action="store_true",
        help="Authenticate and print the account credit balance without generating",
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="Optional requested duration; omit for accounts without this feature",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_local_env(ASSET_SOURCE_ROOT / ".env")
    try:
        client = SayMotionClient(
            os.getenv("SAYMOTION_API_URL", ""),
            os.getenv("SAYMOTION_CLIENT_ID", ""),
            os.getenv("SAYMOTION_CLIENT_SECRET", ""),
        )
        print("Authenticating with SayMotion...")
        client.authenticate()
        if args.credits:
            print(json.dumps(client.get_credit_balance(), ensure_ascii=False, indent=2))
            return 0
        available_credits = require_available_credits(client.get_credit_balance())
        print(f"Available SayMotion API credits: {available_credits:g}")
        models = client.list_models()
        if args.list_models:
            for model in models:
                model_id = str(model.get("id", model.get("Id", "")))
                model_name = str(
                    model.get("name", model.get("modelName", model.get("displayName", "unnamed")))
                )
                model_type = str(model.get("type", model.get("modelType", "unknown")))
                print(f"{model_id}\t{model_name}\t{model_type}")
            return 0
        model_id = select_model(models, args.model_id)
        print(f"Submitting motion job with character model {model_id}...")
        rid = client.submit(args.prompt, model_id, args.duration)
        client.wait_for_job(rid, args.timeout)
        client.download(client.get_glb_url(rid), args.output)
        print(f"Saved generated GLB to {args.output}")
        return 0
    except (SayMotionError, ValueError) as error:
        print(f"SayMotion generation failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
