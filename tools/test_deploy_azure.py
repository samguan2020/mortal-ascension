"""Deployment safety tests; no Azure or model requests."""

import argparse
import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import deploy_azure as deployment


def options(**overrides):
    values = dict(
        subscription="subscription", resource_group="rg-ai-town",
        environment="environment", identity="identity", registry="registry",
        app="tingyu-inn", image="tingyu-inn:verified",
    )
    return argparse.Namespace(**{**values, **overrides})


class DeploymentTests(unittest.TestCase):
    def test_curated_build_context_contains_only_runtime_files_and_is_removed(self):
        staged = []

        def cli(*args):
            if args[:2] == ("acr", "build"):
                root = Path(args[-1])
                staged.append(root)
                paths = [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()]
                self.assertIn("web/public/characters/liu_innkeeper_animated.glb", paths)
                self.assertIn("backend/npc_roles.py", paths)
                self.assertIn("backend/relationship_manager.py", paths)
                self.assertIn("cloud/server.py", paths)
                self.assertFalse(any(
                    ".env" in name or "prototypes/" in name or ".blend" in name or ".git/" in name
                    for name in paths
                ))
                return {"runId": "mock"}
            return {"status": "Succeeded"}

        with patch.object(deployment, "cli", side_effect=cli), contextlib.redirect_stdout(io.StringIO()):
            image = deployment.build_image(options())
        self.assertTrue(image.startswith("tingyu-inn:"))
        self.assertFalse(staged[0].exists())

    def test_existing_password_is_preserved_and_secrets_are_not_cli_arguments(self):
        old_password = "existing-private-password"
        secret_key = "test-only-llm-key"
        sent = []

        def cli(*args):
            self.assertNotIn(secret_key, args)
            self.assertNotIn(old_password, args)
            if args[:3] == ("containerapp", "env", "show"):
                return {"id": "/environment", "location": "eastus2",
                        "properties": {"provisioningState": "Succeeded", "defaultDomain": "example.com"}}
            if args[:2] == ("identity", "show"):
                return {"id": "/identity"}
            if args[:2] == ("account", "get-access-token"):
                return {"accessToken": "test-token"}
            if args[:2] == ("containerapp", "list"):
                return [{"name": "tingyu-inn"}]
            self.fail(f"Unexpected CLI command: {args[:2]}")

        def arm(method, resource, token, body=None):
            if method == "POST":
                return {"value": [{"name": "site-password", "value": old_password}]}
            if method == "PUT":
                sent.append(body)
                return {}
            return {"properties": {"provisioningState": "Succeeded", "latestReadyRevisionName": "ready"}}

        values = {"LLM_API_KEY": secret_key, "LLM_MODEL_ID": "model", "LLM_BASE_URL": "https://example.org/v1"}
        output = io.StringIO()
        with patch.object(deployment, "cli", side_effect=cli), patch.object(deployment, "arm", side_effect=arm), \
                patch.object(deployment, "dotenv_values", return_value=values), contextlib.redirect_stdout(output):
            url = deployment.deploy(options())
        self.assertEqual(url, "https://tingyu-inn.example.com")
        properties = sent[0]["properties"]
        self.assertFalse(properties["configuration"]["ingress"]["allowInsecure"])
        self.assertEqual(properties["template"]["scale"]["maxReplicas"], 1)
        self.assertEqual(properties["configuration"]["secrets"][0]["value"], old_password)
        self.assertNotIn(old_password, output.getvalue())
        self.assertNotIn(secret_key, output.getvalue())

    def test_missing_credentials_stop_before_build_or_cloud_requests(self):
        with patch.object(deployment, "dotenv_values", return_value={}), patch.object(deployment, "cli") as cli:
            with self.assertRaisesRegex(RuntimeError, "Missing backend configuration"):
                deployment.deploy(options())
            cli.assert_not_called()


if __name__ == "__main__":
    unittest.main()
