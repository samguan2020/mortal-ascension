"""Build a curated source bundle and deploy the private Azure preview.

Run with the backend virtualenv. Azure CLI supplies the current login; credentials
are sent to Azure Resource Manager in memory, never in command arguments/files.
"""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ARM = "https://management.azure.com"
API_VERSION = "2024-03-01"


def cli(*arguments: str) -> object:
    """Run Azure CLI without streaming possibly confidential output."""
    executable = shutil.which("az")
    if not executable:
        raise RuntimeError("Azure CLI is not installed or not on PATH")
    result = subprocess.run(
        [executable, *arguments, "--output", "json", "--only-show-errors"],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Azure CLI {arguments[0]} {arguments[1]} failed: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def arm(method: str, resource: str, token: str, body: dict | None = None) -> dict:
    """Send an authenticated ARM request without logging its secret-bearing body."""
    request = Request(
        f"{ARM}{resource}?api-version={API_VERSION}",
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps(body).encode("utf-8") if body is not None else None,
    )
    try:
        with urlopen(request, timeout=120) as response:
            return json.load(response)
    except HTTPError as error:
        # Only Azure's error code is safe to report; messages may echo input.
        try:
            payload = json.loads(error.read())
            code = payload.get("error", {}).get("code", "Unknown")
        except (ValueError, AttributeError):
            code = "UnreadableError"
        raise RuntimeError(f"Azure ARM {method} failed: HTTP {error.code}, code={code}") from None


def build_image(args: argparse.Namespace) -> str:
    """Upload only approved runtime files to ACR; exclude local env and prototypes."""
    tag = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    image = f"tingyu-inn:{tag}"
    files = [
        ".dockerignore", "cloud/Dockerfile", "cloud/requirements.txt", "cloud/server.py",
        "backend/npc_roles.py", "backend/relationship_manager.py",
        "web/package.json", "web/package-lock.json",
        "web/tsconfig.json", "web/index.html",
        "web/public/characters/liu_innkeeper_animated.glb",
        "web/public/characters/player_traveler_animated.glb",
    ]
    files.extend(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "web" / "src").rglob("*")
        if path.is_file() and path.suffix in {".ts", ".css"}
    )
    with tempfile.TemporaryDirectory(prefix="ai-town-build-") as temporary:
        staging = Path(temporary)
        for relative in files:
            source = ROOT / relative
            if not source.is_file() or source.is_symlink():
                raise RuntimeError(f"Missing or unsafe build input: {relative}")
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        print(f"Submitting {len(files)} curated runtime files to ACR...", flush=True)
        result = cli(
            "acr", "build", "--registry", args.registry, "--subscription", args.subscription,
            "--image", image, "--file", "cloud/Dockerfile", "--platform", "linux/amd64",
            "--timeout", "1800", "--no-logs", str(staging),
        )
        if not isinstance(result, dict) or "runId" not in result:
            raise RuntimeError("ACR did not return a build run ID")
        run_id = result["runId"]
        deadline = time.monotonic() + 1900
        while time.monotonic() < deadline:
            run = cli("acr", "task", "show-run", "--registry", args.registry,
                      "--subscription", args.subscription, "--run-id", run_id)
            status = run.get("status") if isinstance(run, dict) else None
            if status == "Succeeded":
                print(f"Image build succeeded: {image}", flush=True)
                return image
            if status in {"Failed", "Canceled", "Error", "Timeout"}:
                raise RuntimeError(f"ACR build {run_id}: {status}; inspect az acr task logs")
            time.sleep(10)
        raise RuntimeError(f"ACR build {run_id} exceeded deployment wait budget")


def deploy(args: argparse.Namespace) -> str:
    """Deploy a password-protected, single-replica app using managed image pulls."""
    values = dotenv_values(ROOT / "backend" / ".env")
    required = ("LLM_API_KEY", "LLM_MODEL_ID", "LLM_BASE_URL")
    provider = str(values.get("LLM_PROVIDER") or "openai_compatible")
    if provider not in {"openai_compatible", "azure_openai"}:
        raise RuntimeError("LLM_PROVIDER must be openai_compatible or azure_openai")
    if provider == "azure_openai":
        required += ("LLM_API_VERSION",)
    elif values.get("LLM_API_VERSION"):
        raise RuntimeError("LLM_API_VERSION is only valid for azure_openai")
    missing = [name for name in required if not values.get(name)]
    if missing:
        raise RuntimeError(f"Missing backend configuration: {', '.join(missing)}")
    if not str(values["LLM_BASE_URL"]).startswith("https://"):
        raise RuntimeError("Cloud LLM endpoint must use HTTPS")
    prefix = f"/subscriptions/{args.subscription}/resourceGroups/{args.resource_group}"
    environment = cli(
        "containerapp", "env", "show", "--name", args.environment,
        "--resource-group", args.resource_group, "--subscription", args.subscription,
    )
    if not isinstance(environment, dict) or environment["properties"]["provisioningState"] != "Succeeded":
        raise RuntimeError("Container Apps environment is not ready")
    identity = cli("identity", "show", "--name", args.identity,
                   "--resource-group", args.resource_group, "--subscription", args.subscription)
    if not isinstance(identity, dict):
        raise RuntimeError("Image pull identity was not found")
    image = args.image or build_image(args)
    credentials = cli("account", "get-access-token", "--subscription", args.subscription,
                      "--resource", ARM)
    if not isinstance(credentials, dict):
        raise RuntimeError("Azure login did not provide an access token")
    token = credentials["accessToken"]
    resource = f"{prefix}/providers/Microsoft.App/containerApps/{args.app}"
    password = secrets.token_urlsafe(32)
    existing = cli("containerapp", "list", "--resource-group", args.resource_group,
                   "--subscription", args.subscription)
    if not isinstance(existing, list):
        raise RuntimeError("Could not check for an existing app")
    if any(item["name"] == args.app for item in existing):
        prior = arm("POST", resource + "/listSecrets", token)
        matched = next((item for item in prior.get("value", []) if item["name"] == "site-password"), None)
        if not matched or not matched.get("value"):
            raise RuntimeError("Existing app has no site password; refusing silent password rotation")
        password = matched["value"]
    origin = f"https://{args.app}.{environment['properties']['defaultDomain']}"
    configuration = {
        "activeRevisionsMode": "Single",
        "secrets": [
            {"name": "site-password", "value": password},
            {"name": "llm-api-key", "value": values["LLM_API_KEY"]},
        ],
        "registries": [{"server": f"{args.registry}.azurecr.io", "identity": identity["id"]}],
        "ingress": {
            "external": True, "targetPort": 8000, "transport": "auto",
            "allowInsecure": False,
            "traffic": [{"latestRevision": True, "weight": 100}],
        },
    }
    environment_variables = [
        {"name": "SITE_PASSWORD", "secretRef": "site-password"},
        {"name": "LLM_API_KEY", "secretRef": "llm-api-key"},
        {"name": "LLM_MODEL_ID", "value": values["LLM_MODEL_ID"]},
        {"name": "LLM_BASE_URL", "value": values["LLM_BASE_URL"]},
        {"name": "LLM_PROVIDER", "value": provider},
        {"name": "PUBLIC_ORIGIN", "value": origin},
    ]
    if values.get("LLM_API_VERSION"):
        environment_variables.append(
            {"name": "LLM_API_VERSION", "value": values["LLM_API_VERSION"]}
        )
    probe = {
        "httpGet": {"path": "/healthz", "port": 8000},
        "periodSeconds": 10, "timeoutSeconds": 3,
    }
    body = {
        "location": environment["location"],
        "tags": {"project": "ai-town", "purpose": "private-preview"},
        "identity": {"type": "UserAssigned", "userAssignedIdentities": {identity["id"]: {}}},
        "properties": {
            "managedEnvironmentId": environment["id"],
            "workloadProfileName": "Consumption",
            "configuration": configuration,
            "template": {
                "containers": [{
                    "name": "game", "image": f"{args.registry}.azurecr.io/{image}",
                    "resources": {"cpu": 0.5, "memory": "1Gi"},
                    "env": environment_variables,
                    "probes": [
                        {**probe, "type": "Startup", "failureThreshold": 30},
                        {**probe, "type": "Readiness", "failureThreshold": 3},
                        {**probe, "type": "Liveness", "failureThreshold": 6},
                    ],
                }],
                "scale": {"minReplicas": 0, "maxReplicas": 1,
                          "rules": [{"name": "http", "http": {"metadata": {"concurrentRequests": "10"}}}]},
            },
        },
    }
    arm("PUT", resource, token, body)
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        state = arm("GET", resource, token)
        properties = state["properties"]
        if properties.get("provisioningState") == "Failed":
            raise RuntimeError("Container App revision provisioning failed; inspect system logs")
        if properties.get("provisioningState") == "Succeeded" and properties.get("latestReadyRevisionName"):
            print(f"Ready: {origin}", flush=True)
            return origin
        time.sleep(10)
    raise RuntimeError("Container App readiness exceeded deployment wait budget")


def main() -> None:
    """Parse the explicitly selected Azure resources and run deployment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", default="rg-ai-town")
    parser.add_argument("--environment", default="ai-town-env-eastus2")
    parser.add_argument("--registry", default="aitownfd6715")
    parser.add_argument("--identity", default="ai-town-image-pull")
    parser.add_argument("--app", default="tingyu-inn")
    parser.add_argument("--image", help="Use an existing registry image tag instead of rebuilding")
    args = parser.parse_args()
    try:
        deploy(args)
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        raise SystemExit(f"Deployment failed: {error}") from None


if __name__ == "__main__":
    main()
