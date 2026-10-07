"""Network-free cloud contract tests: python -m unittest cloud.test_server -v."""

import asyncio
import base64
import json
import secrets
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.npc_roles import NPC_ROLES, create_system_prompt
from cloud.server import (
    LOCAL_SESSION_COOKIE, MAX_BODY_BYTES, SESSION_COOKIE, SecurityBoundary, Settings,
    create_app, make_agent_factory,
)
from tools.run_local import load_local_settings

NPC = next(name for name, role in NPC_ROLES.items() if "setting" in role)
ORIGIN = "https://town.example"
LOCAL_ORIGIN = "http://127.0.0.1:5174"


class FakeAgent:
    def __init__(self):
        self.messages = []
        self.relationship_contexts = []

    def reply(self, message, relationship_context=""):
        self.messages.append(message)
        self.relationship_contexts.append(relationship_context)
        return f"reply {len(self.messages)}"


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / "index.html").write_text("<html>Independent town client</html>", encoding="utf-8")
        (root / "characters").mkdir()
        (root / "characters" / "liu.glb").write_bytes(b"test character")
        (root / "assets").mkdir()
        (root / "assets" / "main.js").write_text("export {};", encoding="utf-8")
        self.settings = Settings(
            site_password=secrets.token_urlsafe(48),
            public_origin=ORIGIN,
            llm_model_id="configured-model",
            llm_base_url="https://provider.example/v1",
            llm_api_key=secrets.token_urlsafe(32),
            static_dir=root,
        )
        self.now = 1000.0
        self.agents = []

    def factory(self, _name):
        agent = FakeAgent()
        self.agents.append(agent)
        return agent

    def client(self, **overrides):
        settings = replace(self.settings, **overrides)
        app = create_app(settings, self.factory, clock=lambda: self.now)
        return TestClient(app, base_url=ORIGIN)

    def chat(self, client, message="hello", npc_name=NPC, origin=ORIGIN):
        headers = {"Origin": origin} if origin is not None else {}
        return client.post(
            "/api/chat", json={"npc_name": npc_name, "message": message},
            headers=headers, auth=("player", self.settings.site_password),
        )

    def test_healthz_is_anonymous_and_never_creates_agents(self):
        with self.client() as client:
            for _ in range(3):
                self.assertEqual(client.get("/healthz").json(), {"status": "ok"})
        self.assertEqual(self.agents, [])

    def test_all_static_and_api_routes_require_basic_auth(self):
        with self.client() as client:
            for route in [
                "/", "/assets/main.js", "/characters/liu.glb", "/api/health",
                "/api/session", "/api/chat", "/docs",
            ]:
                with self.subTest(route=route):
                    response = client.get(route)
                    self.assertEqual(response.status_code, 401)
                    self.assertIn("Basic", response.headers["www-authenticate"])
                    self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(client.head("/").status_code, 401)
            self.assertEqual(client.options("/api/chat").status_code, 401)
            self.assertEqual(client.post("/healthz").status_code, 401)

    def test_invalid_and_malformed_credentials_are_rejected(self):
        with self.client() as client:
            for auth in [("player", "wrong"), ("other", self.settings.site_password)]:
                self.assertEqual(client.get("/", auth=auth).status_code, 401)
            for value in ["Basic !!!", "Bearer token", "Basic " + "a" * 3000,
                          "Basic " + base64.b64encode(b"\xff:bad").decode()]:
                self.assertEqual(client.get("/", headers={"Authorization": value}).status_code, 401)

    def test_authenticated_static_and_capability_health(self):
        with self.client() as client:
            auth = ("player", self.settings.site_password)
            for path in ["/", "/characters/liu.glb", "/assets/main.js"]:
                self.assertEqual(client.get(path, auth=auth).status_code, 200)
            response = client.get("/api/health", auth=auth)
            self.assertTrue(response.json()["chat_enabled"])
            self.assertEqual(response.json()["provider_status"], "configured_not_probed")
            self.assertIn(NPC, response.json()["npc_names"])
            self.assertNotIn(self.settings.site_password, response.text)
            self.assertNotIn(self.settings.llm_api_key, response.text)
            self.assertEqual(client.get("/api/missing", auth=auth).status_code, 404)
        self.assertEqual(self.agents, [])

    def test_success_shape_and_secure_cookie(self):
        with self.client() as client:
            response = self.chat(client)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {
                "npc_name": NPC, "npc_title": NPC_ROLES[NPC]["title"],
                "message": "reply 1", "success": True,
            })
            cookie = response.headers["set-cookie"]
            for flag in [SESSION_COOKIE, "Secure", "HttpOnly", "SameSite=strict", "Path=/"]:
                self.assertIn(flag, cookie)
            self.assertNotIn("Domain=", cookie)
            self.assertEqual(self.chat(client).json()["message"], "reply 2")

    def test_origins_missing_null_foreign_and_cross_site_rejected(self):
        with self.client() as client:
            for origin in [None, "null", "https://foreign.example", ORIGIN + ".evil", ORIGIN + "/"]:
                self.assertEqual(self.chat(client, origin=origin).status_code, 403)
            response = client.post(
                "/api/chat", json={"npc_name": NPC, "message": "hello"},
                auth=("player", self.settings.site_password),
                headers={"Origin": ORIGIN, "Sec-Fetch-Site": "cross-site"},
            )
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.agents, [])

    def test_local_development_is_loopback_only_without_basic_auth(self):
        settings = replace(
            self.settings, public_origin=LOCAL_ORIGIN, static_dir=None, local_development=True,
        )
        app = create_app(settings, self.factory, clock=lambda: self.now)
        with TestClient(app, base_url=LOCAL_ORIGIN, client=("127.0.0.1", 50000)) as client:
            response = client.post(
                "/api/chat", json={"npc_name": NPC, "message": "hello"},
                headers={"Origin": LOCAL_ORIGIN},
            )
            self.assertEqual(response.status_code, 200)
            cookie = response.headers["set-cookie"]
            self.assertIn(LOCAL_SESSION_COOKIE, cookie)
            self.assertIn("HttpOnly", cookie)
            self.assertIn("SameSite=strict", cookie)
            self.assertNotIn("Secure", cookie)
            self.assertEqual(
                client.post(
                    "/api/chat", json={"npc_name": NPC, "message": "hello"},
                    headers={"Origin": "http://127.0.0.1:5173"},
                ).status_code,
                403,
            )
        with TestClient(app, base_url=LOCAL_ORIGIN, client=("192.0.2.1", 50000)) as client:
            self.assertEqual(client.get("/api/health").status_code, 403)

    def test_validation_exact_500_character_boundary(self):
        with self.client() as client:
            for message in ["", "   ", "a" * 501, 12, None]:
                response = self.chat(client, message=message)
                self.assertEqual(response.status_code, 422)
                self.assertFalse(response.json()["success"])
            self.assertEqual(self.chat(client, npc_name="unknown").status_code, 422)
            self.assertEqual(self.chat(client, message="a" * 500).status_code, 200)
        self.assertEqual(len(self.agents), 1)

    def test_invalid_json_extra_fields_body_size_and_content_type(self):
        with self.client() as client:
            auth = ("player", self.settings.site_password)
            headers = {"Origin": ORIGIN, "Content-Type": "application/json"}
            for body in ["{", "[]", '{"npc_name":"unknown"}',
                         json.dumps({"npc_name": NPC, "message": "hello", "extra": True})]:
                self.assertEqual(client.post("/api/chat", content=body, auth=auth, headers=headers).status_code, 422)
            self.assertEqual(client.post(
                "/api/chat", content="x" * (MAX_BODY_BYTES + 1), auth=auth, headers=headers,
            ).status_code, 413)
            self.assertEqual(client.post(
                "/api/chat", content="hello", auth=auth, headers={"Origin": ORIGIN},
            ).status_code, 415)
        self.assertEqual(self.agents, [])

    def test_separate_browser_sessions_and_forged_cookie(self):
        with self.client() as client:
            self.assertEqual(self.chat(client, "first browser").json()["message"], "reply 1")
            first_cookie = client.cookies.get(SESSION_COOKIE)
            client.cookies.clear()
            client.cookies.set(SESSION_COOKIE, "attacker-chosen-id")
            self.assertEqual(self.chat(client, "second browser").json()["message"], "reply 1")
            self.assertNotEqual(client.cookies.get(SESSION_COOKIE, domain="town.example", path="/"),
                                "attacker-chosen-id")
            client.cookies.clear()
            client.cookies.set(SESSION_COOKIE, first_cookie)
            self.assertEqual(self.chat(client, "first again").json()["message"], "reply 2")
        self.assertEqual(self.agents[0].messages, ["first browser", "first again"])
        self.assertEqual(self.agents[1].messages, ["second browser"])

    def test_only_cultivation_innkeeper_is_available(self):
        with self.client() as client:
            self.assertEqual(list(NPC_ROLES), ["柳掌柜"])
            self.assertEqual(self.chat(client, "innkeeper").status_code, 200)
            self.assertEqual(self.chat(client, "unknown character", "张三").status_code, 422)
        self.assertEqual(len(self.agents), 1)

    def test_session_log_restores_last_eight_successful_turns(self):
        with self.client(session_requests_per_minute=20) as client:
            initial = client.get(
                "/api/session", auth=("player", self.settings.site_password)
            )
            self.assertEqual(initial.status_code, 200)
            self.assertEqual(initial.json()["messages"], [])
            for number in range(10):
                self.assertEqual(self.chat(client, f"turn {number}").status_code, 200)
            restored = client.get(
                "/api/session", auth=("player", self.settings.site_password)
            ).json()
        self.assertEqual(restored["memory_turns"], 8)
        self.assertEqual(restored["max_memory_turns"], 8)
        self.assertEqual(restored["messages"][0], {
            "role": "player", "message": "turn 2",
        })
        self.assertEqual(restored["messages"][-1], {
            "role": "npc", "message": "reply 10",
        })

    def test_hidden_affinity_changes_prompt_context_without_response_fields(self):
        with self.client() as client:
            response = self.chat(client, "你好")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("affinity", response.json())
            self.assertIn("客气", self.agents[0].relationship_contexts[0])
            response = self.chat(client, "滚")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("affinity", response.json())
            self.assertIn("客气", self.agents[0].relationship_contexts[1])
            response = self.chat(client, "滚开，老东西")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("affinity", response.json())
            self.assertIn("疏离", self.agents[0].relationship_contexts[2])

    def test_session_expiry_and_capacity_are_bounded(self):
        with self.client(max_sessions=1, session_ttl_seconds=30) as client:
            self.chat(client)
            client.cookies.clear()
            self.assertEqual(self.chat(client).status_code, 429)
            self.now += 31
            self.assertEqual(self.chat(client).json()["message"], "reply 1")
        self.assertEqual(len(self.agents), 2)

    def test_session_and_global_rate_limits(self):
        with self.client(session_requests_per_minute=1, requests_per_minute=2) as client:
            self.assertEqual(self.chat(client).status_code, 200)
            response = self.chat(client)
            self.assertEqual(response.status_code, 429)
            self.assertIn("retry-after", response.headers)
            client.cookies.clear()
            self.assertEqual(self.chat(client).status_code, 200)
            client.cookies.clear()
            self.assertEqual(self.chat(client).status_code, 429)
            self.now += 60
            self.assertEqual(self.chat(client).status_code, 200)

    def test_daily_budget_cannot_be_bypassed_by_new_browser(self):
        with self.client(requests_per_day=1) as client:
            self.assertEqual(self.chat(client).status_code, 200)
            client.cookies.clear()
            self.now += 3600
            self.assertEqual(self.chat(client).status_code, 429)
            self.now += 86400
            self.assertEqual(self.chat(client).status_code, 200)

    def test_provider_errors_are_explicit_sanitized_and_consume_budget(self):
        def failing_factory(_name):
            raise RuntimeError(self.settings.llm_api_key)

        self.factory = failing_factory
        with self.client(requests_per_day=1) as client:
            with self.assertLogs("ai_town.cloud", level="WARNING") as logs:
                response = self.chat(client)
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json()["error"]["code"], "provider_error")
            self.assertNotIn(self.settings.llm_api_key, response.text + str(logs.output))
            self.assertEqual(self.chat(client).status_code, 429)

    def test_empty_and_invalid_provider_responses_are_errors(self):
        for value in [None, "", "  ", "a" * 2001]:
            with self.subTest(value_type=type(value).__name__):
                agent = FakeAgent()
                agent.reply = lambda _message, _context="": value
                self.factory = lambda _name: agent
                with self.client() as client, self.assertLogs("ai_town.cloud", level="WARNING"):
                    self.assertEqual(self.chat(client).status_code, 502)

    def test_timeout_keeps_concurrency_slot_until_worker_finishes(self):
        release = threading.Event()
        finished = threading.Event()

        class SlowAgent:
            def reply(self, _message, _context=""):
                if not release.wait(5):
                    raise TimeoutError("Test worker was not released")
                finished.set()
                return "late answer"

        self.factory = lambda _name: SlowAgent()
        with self.client(chat_timeout_seconds=0.01, max_concurrent=1) as client:
            try:
                with self.assertLogs("ai_town.cloud", level="WARNING"):
                    self.assertEqual(self.chat(client).status_code, 504)
                client.cookies.clear()
                self.assertEqual(self.chat(client).status_code, 429)
            finally:
                release.set()
                self.assertTrue(finished.wait(2))

    def test_provider_failure_discards_the_affected_session_agent(self):
        created = []

        class OnceFailingAgent(FakeAgent):
            def reply(self, message, relationship_context=""):
                if message == "fail":
                    raise RuntimeError("upstream unavailable")
                return super().reply(message, relationship_context)

        def factory(name):
            agent = OnceFailingAgent()
            created.append((name, agent))
            return agent

        self.factory = factory
        with self.client() as client:
            self.chat(client)
            with self.assertLogs("ai_town.cloud", level="WARNING"):
                self.assertEqual(self.chat(client, "fail").status_code, 502)
            self.assertEqual(self.chat(client).json()["message"], "reply 1")
        self.assertEqual(len(created), 2)

    def test_same_browser_cannot_mutate_an_agent_concurrently(self):
        entered = threading.Event()
        release = threading.Event()

        class BlockingAgent(FakeAgent):
            def reply(self, message, relationship_context=""):
                if message == "block":
                    entered.set()
                    if not release.wait(5):
                        raise TimeoutError("Test worker was not released")
                return super().reply(message, relationship_context)

        self.factory = lambda _name: BlockingAgent()
        replies = []
        with self.client(max_concurrent=2) as client:
            self.chat(client)
            worker = threading.Thread(target=lambda: replies.append(self.chat(client, "block")))
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(self.chat(client).status_code, 429)
            finally:
                release.set()
                worker.join(timeout=5)
                self.assertFalse(worker.is_alive())
        self.assertEqual(replies[0].json()["message"], "reply 2")

    def test_settings_fail_closed(self):
        cases = [
            {"site_password": "short"}, {"site_password": "a" * 64},
            {"public_origin": ""}, {"public_origin": "http://town.example"},
            {"public_origin": ORIGIN + "/"}, {"public_origin": ORIGIN + "?secret=x"},
            {"llm_api_key": ""}, {"llm_api_key": "your-api-key"}, {"llm_model_id": ""},
            {"llm_base_url": "https://user:secret@provider.example"},
            {"llm_base_url": "http://provider.example"}, {"llm_base_url": "https://host:bad"},
            {"llm_timeout_seconds": 0}, {"chat_timeout_seconds": float("nan")},
            {"max_concurrent": 99}, {"static_dir": Path(self.temp.name) / "missing"},
        ]
        for changes in cases:
            with self.subTest(fields=list(changes)):
                with self.assertRaises(ValueError):
                    with self.client(**changes):
                        pass
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(ValueError):
            Settings.from_env()

    def test_local_settings_load_only_required_provider_values(self):
        config = Path(self.temp.name) / ".env"
        config.write_text(
            "LLM_API_KEY=local-provider-key\n"
            "LLM_MODEL_ID=local-model\n"
            "LLM_BASE_URL=https://provider.example/v1\n"
            "OBSOLETE_VALUE=ignored\n",
            encoding="utf-8",
        )
        settings = load_local_settings(config, 5174)
        self.assertTrue(settings.local_development)
        self.assertEqual(settings.public_origin, LOCAL_ORIGIN)
        self.assertIsNone(settings.static_dir)
        self.assertFalse(hasattr(settings, "obsolete_value"))

        config.write_text("LLM_API_KEY=only-one-value\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Missing local provider configuration"):
            load_local_settings(config, 5174)

    def test_production_factory_initialization_failure_is_sanitized(self):
        with patch("cloud.server.make_agent_factory", side_effect=RuntimeError(self.settings.llm_api_key)):
            with self.assertLogs("ai_town.cloud", level="ERROR") as logs:
                with self.assertRaisesRegex(RuntimeError, "Cloud LLM initialization failed") as raised:
                    with TestClient(create_app(self.settings)):
                        pass
        self.assertNotIn(self.settings.llm_api_key, str(raised.exception) + str(logs.output))

    def test_real_helloagents_adapter_preserves_prompt_and_caps_history_without_network(self):
        factory = make_agent_factory(self.settings)
        from hello_agents import HelloAgentsLLM

        calls = []

        def invoke(llm, messages, **_kwargs):
            calls.append(messages)
            self.assertEqual(llm._client.max_retries, 0)
            self.assertEqual(llm.timeout, self.settings.llm_timeout_seconds)
            self.assertEqual(llm.max_tokens, self.settings.max_output_tokens)
            return "mock provider reply"

        with patch.object(HelloAgentsLLM, "invoke", invoke):
            agent = factory(NPC)
            for number in range(self.settings.history_turns + 3):
                agent.reply(f"turn {number}")
            isolated = factory(NPC)
            isolated.reply("new browser")
        self.assertEqual(calls[0][0]["content"], create_system_prompt(NPC, NPC_ROLES[NPC]))
        self.assertEqual(len(calls[-2]), 2 + self.settings.history_turns * 2)
        self.assertEqual(calls[-2][1]["content"], "turn 2")
        self.assertEqual(len(calls[-1]), 2)

    def test_production_startup_and_http_chat_use_helloagents_without_paid_call(self):
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="mock completion"))],
        )
        with patch("openai.resources.chat.completions.Completions.create", return_value=completion) as generate:
            with TestClient(create_app(self.settings), base_url=ORIGIN) as client:
                self.assertEqual(client.get("/healthz").status_code, 200)
                generate.assert_not_called()
                self.assertEqual(self.chat(client).json()["message"], "mock completion")
        generate.assert_called_once()
        self.assertEqual(generate.call_args.kwargs["model"], self.settings.llm_model_id)
        self.assertEqual(generate.call_args.kwargs["max_tokens"], self.settings.max_output_tokens)
        self.assertEqual(generate.call_args.kwargs["messages"][0]["content"],
                         create_system_prompt(NPC, NPC_ROLES[NPC]))

    def test_chunked_body_limit_is_enforced_without_content_length(self):
        reached_app = []
        sent = []
        encoded = base64.b64encode(f"player:{self.settings.site_password}".encode())
        scope = {
            "type": "http", "method": "POST", "path": "/api/chat", "scheme": "https",
            "server": ("town.example", 443), "query_string": b"",
            "headers": [(b"authorization", b"Basic " + encoded), (b"origin", ORIGIN.encode()),
                        (b"content-type", b"application/json")],
        }

        async def downstream(_scope, _receive, _send):
            reached_app.append(True)

        async def receive():
            return {"type": "http.request", "body": b"x" * 4096, "more_body": True}

        async def send(message):
            sent.append(message)

        asyncio.run(SecurityBoundary(downstream, lambda: self.settings)(scope, receive, send))
        self.assertEqual(sent[0]["status"], 413)
        self.assertEqual(reached_app, [])


if __name__ == "__main__":
    unittest.main()
