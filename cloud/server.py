"""Same-origin runtime; production never loads dotenv files or local credentials.

Required environment: SITE_PASSWORD (random, >=32 characters), PUBLIC_ORIGIN
(HTTPS origin), LLM_MODEL_ID, LLM_BASE_URL, LLM_API_KEY. Optional:
LLM_PROVIDER (openai_compatible), LLM_API_VERSION (required for azure_openai),
LLM_TIMEOUT_SECONDS (20), CHAT_TIMEOUT_SECONDS (25).
Configuration is validated at startup without a paid provider probe; health
reports configured capability, not verified provider availability.

Run one worker/replica: limits and sessions are process-local, not distributed.
Defaults: 2 concurrent calls, 6/session/minute, 30/process/minute, 500/process/day,
128 sessions, 30-minute idle expiry, 8 turns/NPC, 256 output tokens/call.
Failures consume rate budget; timeouts retain their slot until the worker exits.
History, hidden affinity, dialogue logs, and limits reset on session expiry,
restart, or scale-to-zero. No ambient generation, tools, memory database, or
persistent player data.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import ipaddress
import logging
import os
import re
import secrets
import time
from collections import deque
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.npc_roles import NPC_ROLES, create_system_prompt
from backend.relationship_manager import RelationshipManager

LOGGER = logging.getLogger("ai_town.cloud")
SESSION_COOKIE = "__Host-ai-town-session"
LOCAL_SESSION_COOKIE = "mortal-ascension-local-session"
MAX_BODY_BYTES = 8192


@dataclass(frozen=True)
class Settings:
    """Explicit server settings; secrets are omitted from representations."""

    site_password: str = field(repr=False)
    public_origin: str
    llm_model_id: str
    llm_base_url: str = field(repr=False)
    llm_api_key: str = field(repr=False)
    llm_provider: str = "openai_compatible"
    llm_api_version: str | None = None
    static_dir: Path | None = Path("/app/web/dist")
    local_development: bool = False
    llm_timeout_seconds: int = 20
    chat_timeout_seconds: float = 25
    max_concurrent: int = 2
    session_requests_per_minute: int = 6
    requests_per_minute: int = 30
    requests_per_day: int = 500
    max_sessions: int = 128
    session_ttl_seconds: int = 1800
    history_turns: int = 8
    max_output_tokens: int = 256

    @classmethod
    def from_env(cls) -> Settings:
        """Read only process environment, never local credential files."""
        required = (
            "SITE_PASSWORD", "PUBLIC_ORIGIN", "LLM_MODEL_ID",
            "LLM_BASE_URL", "LLM_API_KEY",
        )
        if any(not os.environ.get(key, "").strip() for key in required):
            raise ValueError("Missing required cloud runtime environment variables")
        try:
            return cls(
                site_password=os.environ["SITE_PASSWORD"],
                public_origin=os.environ["PUBLIC_ORIGIN"],
                llm_model_id=os.environ["LLM_MODEL_ID"],
                llm_base_url=os.environ["LLM_BASE_URL"],
                llm_api_key=os.environ["LLM_API_KEY"],
                llm_provider=os.environ.get("LLM_PROVIDER", "openai_compatible"),
                llm_api_version=os.environ.get("LLM_API_VERSION") or None,
                llm_timeout_seconds=int(os.environ.get("LLM_TIMEOUT_SECONDS", "20")),
                chat_timeout_seconds=float(os.environ.get("CHAT_TIMEOUT_SECONDS", "25")),
            )
        except ValueError:
            raise ValueError("Invalid cloud runtime environment configuration") from None

    def validate(self) -> None:
        """Fail startup on missing, unsafe, or unbounded configuration."""
        if (
            len(self.site_password) < 32
            or len(set(self.site_password)) < 12
            or not self.site_password.isascii()
            or any(character.isspace() for character in self.site_password)
        ):
            raise ValueError("SITE_PASSWORD must be a high-entropy ASCII secret (>=32 characters)")
        for name, value in (
            ("LLM_MODEL_ID", self.llm_model_id), ("LLM_API_KEY", self.llm_api_key),
        ):
            if not value.strip() or value != value.strip() or value.lower() in {
                "changeme", "placeholder", "your-api-key", "your_api_key", "test", "none",
            }:
                raise ValueError(f"{name} must contain real provider configuration")
        if self.llm_provider not in {"openai_compatible", "azure_openai"}:
            raise ValueError("LLM_PROVIDER must be openai_compatible or azure_openai")
        if self.llm_provider == "azure_openai":
            if not self.llm_api_version or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}(?:-preview)?", self.llm_api_version
            ):
                raise ValueError("Azure OpenAI requires a valid LLM_API_VERSION")
        elif self.llm_api_version is not None:
            raise ValueError("LLM_API_VERSION is only valid for azure_openai")
        for name, value in (("PUBLIC_ORIGIN", self.public_origin), ("LLM_BASE_URL", self.llm_base_url)):
            try:
                url = urlsplit(value)
                valid = (
                    url.hostname and url.port != 0 and not url.username and not url.password
                    and not url.query and not url.fragment
                    and not any(character.isspace() for character in value)
                )
                if name == "PUBLIC_ORIGIN":
                    if self.local_development:
                        valid = (
                            valid and url.scheme == "http" and url.hostname == "127.0.0.1"
                            and url.port is not None and not url.path
                            and value == f"http://{url.netloc}"
                        )
                    else:
                        valid = valid and url.scheme == "https" and not url.path and value == f"https://{url.netloc}"
                else:
                    valid = valid and url.scheme == "https"
                    if self.llm_provider == "azure_openai":
                        valid = valid and url.path in {"", "/"}
                if not valid:
                    raise ValueError
            except ValueError:
                expected = "loopback HTTP origin" if name == "PUBLIC_ORIGIN" and self.local_development else "HTTPS URL"
                raise ValueError(f"{name} must be a valid {expected} (origin only for PUBLIC_ORIGIN)") from None
        bounds = (
            (self.llm_timeout_seconds, 1, 60), (self.chat_timeout_seconds, 0.01, 90),
            (self.max_concurrent, 1, 4), (self.session_requests_per_minute, 1, 20),
            (self.requests_per_minute, 1, 100), (self.requests_per_day, 1, 2000),
            (self.max_sessions, 1, 256), (self.session_ttl_seconds, 1, 3600),
            (self.history_turns, 1, 16), (self.max_output_tokens, 1, 512),
        )
        if any(not lower <= value <= upper for value, lower, upper in bounds):
            raise ValueError("Cloud runtime limit outside allowed bounds")
        if not self.local_development and (
            self.static_dir is None or not (self.static_dir / "index.html").is_file()
        ):
            raise ValueError("Built web dist/index.html is required")

    @property
    def session_cookie_name(self) -> str:
        """Return a browser-valid cookie name for the active transport."""
        return LOCAL_SESSION_COOKIE if self.local_development else SESSION_COOKIE


class ChatAgent(Protocol):
    """One session-local NPC with bounded synchronous conversation."""

    def reply(self, message: str, relationship_context: str = "") -> str: ...


AgentFactory = Callable[[str], ChatAgent]


def make_agent_factory(settings: Settings) -> AgentFactory:
    """Construct core HelloAgents only, with no retries or network startup call."""
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    from hello_agents import HelloAgentsLLM, SimpleAgent
    from openai import AzureOpenAI

    class NoRetryLLM(HelloAgentsLLM):
        def _create_client(self):
            # HelloAgents 0.2.9 does not forward retry settings to OpenAI.
            return super()._create_client().with_options(max_retries=0)

    class AzureOpenAILLM(HelloAgentsLLM):
        def _create_client(self):
            return AzureOpenAI(
                api_version=settings.llm_api_version,
                azure_endpoint=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=0,
            )

        def invoke(self, messages: list[dict[str, str]], **kwargs) -> str:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_completion_tokens=kwargs.get(
                    "max_completion_tokens", kwargs.get("max_tokens", self.max_tokens)
                ),
                **{
                    key: value for key, value in kwargs.items()
                    if key not in {"temperature", "max_tokens", "max_completion_tokens"}
                },
            )
            return response.choices[0].message.content

    llm_class = AzureOpenAILLM if settings.llm_provider == "azure_openai" else NoRetryLLM
    llm = llm_class(
        model=settings.llm_model_id,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        provider="custom",
        timeout=settings.llm_timeout_seconds,
        max_tokens=settings.max_output_tokens,
    )

    class BoundedAgent:
        def __init__(self, name: str):
            self.agent = SimpleAgent(
                name=name, llm=llm, system_prompt=create_system_prompt(name, NPC_ROLES[name]),
                enable_tool_calling=False,
            )

        def reply(self, message: str, relationship_context: str = "") -> str:
            prompt = message
            if relationship_context:
                prompt = f"{relationship_context}\n\n【当前对话】\n玩家: {message}"
            response = self.agent.run(prompt)
            if not isinstance(response, str) or not response.strip() or len(response) > 2000:
                raise ValueError("Invalid provider response")
            history = self.agent.get_history()[-settings.history_turns * 2:]
            self.agent.clear_history()
            for item in history:
                self.agent.add_message(item)
            return response

    return BoundedAgent


class ChatInput(BaseModel):
    """Bounded input; unknown fields and NPC names are errors."""

    model_config = ConfigDict(extra="forbid", strict=True)
    npc_name: str = Field(min_length=1, max_length=50)
    message: str = Field(min_length=1, max_length=500)

    @field_validator("npc_name")
    @classmethod
    def known_npc(cls, value: str) -> str:
        if value not in NPC_ROLES:
            raise ValueError("Unknown NPC")
        return value

    @field_validator("message")
    @classmethod
    def nonempty_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        return value.strip()


@dataclass
class Session:
    expires: float
    agents: dict[str, ChatAgent] = field(default_factory=dict)
    requests: deque[float] = field(default_factory=deque)
    dialogue_log: deque[dict[str, str]] = field(default_factory=deque)
    relationships: RelationshipManager = field(default_factory=RelationshipManager)
    busy: bool = False


def error(status: int, code: str, message: str) -> JSONResponse:
    """Return a stable error envelope without reflecting secrets or user input."""
    headers = {"Retry-After": "60"} if status == 429 else {}
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status_code=status, headers=headers,
    )


def authenticated(request: Request, password: str) -> bool:
    """Check Basic credentials using constant-time comparisons."""
    scheme, _, encoded = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "basic" or len(encoded) > 2048:
        return False
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return False
    username, separator, supplied = decoded.partition(":")
    return bool(separator) & secrets.compare_digest(username.encode(), b"player") & secrets.compare_digest(
        supplied.encode(), password.encode()
    )


def is_loopback_client(scope: Scope) -> bool:
    """Return whether the direct HTTP peer is a loopback address."""
    client = scope.get("client")
    if not client:
        return False
    try:
        return ipaddress.ip_address(client[0]).is_loopback
    except ValueError:
        return False


class SecurityBoundary:
    """Protect all HTTP routes and bound request bytes before JSON parsing."""

    def __init__(self, app: ASGIApp, get_settings: Callable[[], Settings]):
        self.app = app
        self.get_settings = get_settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        settings = self.get_settings()

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = list(message["headers"]) + [
                    (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"), (b"referrer-policy", b"same-origin"),
                ]
            await send(message)

        response = None
        if request.method == "GET" and request.url.path == "/healthz":
            pass
        elif settings.local_development and not is_loopback_client(scope):
            response = error(403, "local_only", "Local development is available only on loopback.")
        elif not settings.local_development and not authenticated(request, settings.site_password):
            response = error(401, "authentication_required", "Valid site credentials are required.")
            response.headers["WWW-Authenticate"] = 'Basic realm="Mortal Ascension", charset="UTF-8"'
        elif request.method not in {"GET", "HEAD", "OPTIONS"} and (
            request.headers.get("origin") != settings.public_origin
            or request.headers.get("sec-fetch-site") == "cross-site"
        ):
            response = error(403, "origin_rejected", "A same-origin request is required.")
        elif request.method == "POST":
            if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
                response = error(415, "invalid_content_type", "Use application/json.")
            else:
                body = bytearray()
                try:
                    async with asyncio.timeout(5):
                        while True:
                            event = await receive()
                            if event["type"] == "http.disconnect":
                                return
                            body.extend(event.get("body", b""))
                            if len(body) > MAX_BODY_BYTES:
                                response = error(413, "body_too_large", "Request body is too large.")
                                break
                            if not event.get("more_body", False):
                                break
                except asyncio.TimeoutError:
                    response = error(408, "request_timeout", "Request body took too long.")
                if response is None:
                    delivered = False

                    async def bounded_receive() -> Message:
                        nonlocal delivered
                        if not delivered:
                            delivered = True
                            return {"type": "http.request", "body": bytes(body), "more_body": False}
                        return await receive()

                    await self.app(scope, bounded_receive, secure_send)
                    return
        if response is not None:
            await response(scope, receive, secure_send)
        else:
            await self.app(scope, receive, secure_send)


def create_app(
    settings: Settings | None = None,
    agent_factory: AgentFactory | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> FastAPI:
    """Create an isolated app; injected agents make tests network-free."""
    sessions: dict[str, Session] = {}
    global_requests: deque[float] = deque()
    running: set[asyncio.Task[str | None]] = set()
    active = 0

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        nonlocal settings, agent_factory
        settings = settings if settings is not None else Settings.from_env()
        settings.validate()
        try:
            agent_factory = agent_factory if agent_factory is not None else make_agent_factory(settings)
        except Exception:
            LOGGER.error("Cloud LLM initialization failed")
            raise RuntimeError("Cloud LLM initialization failed; check provider configuration") from None
        if settings.static_dir is not None:
            application.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="web")
        yield
        if running:
            await asyncio.gather(*running, return_exceptions=True)

    application = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    def get_settings() -> Settings:
        assert settings is not None
        return settings

    application.add_middleware(SecurityBoundary, get_settings=get_settings)

    def prune_sessions(now: float) -> None:
        for key in list(sessions):
            if sessions[key].expires <= now and not sessions[key].busy:
                del sessions[key]

    def resolve_session(request: Request, now: float) -> tuple[str, Session] | None:
        assert settings is not None
        prune_sessions(now)
        session_id = request.cookies.get(settings.session_cookie_name, "")
        session = sessions.get(session_id)
        if session is None:
            if len(sessions) >= settings.max_sessions:
                return None
            session_id = secrets.token_urlsafe(32)
            session = Session(expires=now + settings.session_ttl_seconds)
            sessions[session_id] = session
        session.expires = now + settings.session_ttl_seconds
        return session_id, session

    def set_session_cookie(response: JSONResponse, session_id: str) -> None:
        assert settings is not None
        response.set_cookie(
            settings.session_cookie_name, session_id, max_age=settings.session_ttl_seconds,
            secure=not settings.local_development, httponly=True, samesite="strict", path="/",
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exception: RequestValidationError):
        return error(422, "invalid_input", "Use a known NPC and a nonblank message of at most 500 characters.")

    @application.get("/healthz")
    async def liveness():
        return {"status": "ok"}

    @application.get("/api/health")
    async def health():
        return {
            "status": "ok", "chat_enabled": True, "provider_status": "configured_not_probed",
            "memory": "ephemeral", "npc_names": list(NPC_ROLES),
        }

    @application.get("/api/session")
    async def session_state(request: Request):
        assert settings is not None
        resolved = resolve_session(request, clock())
        if resolved is None:
            return error(429, "session_limit", "Too many active browser sessions.")
        session_id, session = resolved
        response = JSONResponse({
            "npc_name": next(iter(NPC_ROLES)),
            "messages": list(session.dialogue_log),
            "memory_turns": len(session.dialogue_log) // 2,
            "max_memory_turns": settings.history_turns,
        })
        set_session_cookie(response, session_id)
        return response

    @application.post("/api/chat")
    async def chat(body: ChatInput, request: Request):
        nonlocal active
        assert settings is not None and agent_factory is not None
        now = clock()
        while global_requests and now - global_requests[0] >= 86400:
            global_requests.popleft()
        if (
            len(global_requests) >= settings.requests_per_day
            or sum(now - stamp < 60 for stamp in global_requests) >= settings.requests_per_minute
        ):
            return error(429, "rate_limited", "The site chat budget is temporarily exhausted.")
        if active >= settings.max_concurrent:
            return error(429, "busy", "Chat is busy; please retry later.")
        resolved = resolve_session(request, now)
        if resolved is None:
            return error(429, "session_limit", "Too many active browser sessions.")
        session_id, session = resolved
        while session.requests and now - session.requests[0] >= 60:
            session.requests.popleft()
        if session.busy or len(session.requests) >= settings.session_requests_per_minute:
            return error(429, "rate_limited", "This browser must wait before chatting again.")
        session.requests.append(now)
        global_requests.append(now)
        session.busy = True
        active += 1
        projected_affinity, _affinity_analysis = session.relationships.projected_affinity(
            body.npc_name, body.message
        )
        relationship_context = (
            "【当前关系】\n"
            f"{session.relationships.get_affinity_level(projected_affinity)}。"
            f"{session.relationships.get_affinity_modifier(projected_affinity)}"
        )

        def invoke() -> str:
            assert agent_factory is not None
            if body.npc_name not in session.agents:
                session.agents[body.npc_name] = agent_factory(body.npc_name)
            result = session.agents[body.npc_name].reply(body.message, relationship_context)
            if not isinstance(result, str) or not result.strip() or len(result) > 2000:
                raise ValueError("Invalid provider response")
            return result

        timed_out = False

        async def generate() -> str | None:
            nonlocal active
            try:
                return await asyncio.to_thread(invoke)
            except Exception:
                # Provider exception text can include credentials, URLs and prompts.
                LOGGER.warning("NPC provider call failed")
                session.agents.pop(body.npc_name, None)
                return None
            finally:
                if timed_out:
                    session.agents.pop(body.npc_name, None)
                session.busy = False
                active -= 1

        task = asyncio.create_task(generate())
        running.add(task)
        task.add_done_callback(running.discard)
        try:
            result = await asyncio.wait_for(asyncio.shield(task), settings.chat_timeout_seconds)
            if result is None:
                response = error(502, "provider_error", "The dialogue provider could not complete the request.")
            else:
                session.relationships.set_affinity(body.npc_name, projected_affinity)
                session.dialogue_log.extend((
                    {"role": "player", "message": body.message},
                    {"role": "npc", "message": result},
                ))
                while len(session.dialogue_log) > settings.history_turns * 2:
                    session.dialogue_log.popleft()
                response = JSONResponse({
                    "npc_name": body.npc_name, "npc_title": NPC_ROLES[body.npc_name]["title"],
                    "message": result, "success": True,
                })
        except asyncio.TimeoutError:
            timed_out = True
            LOGGER.warning("NPC provider call timed out")
            response = error(504, "provider_timeout", "The dialogue provider took too long.")
        except asyncio.CancelledError:
            timed_out = True
            raise
        set_session_cookie(response, session_id)
        return response

    @application.api_route(
        "/api/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    async def unknown_api(path: str):
        return error(404, "not_found", "Unknown API route.")

    return application


app = create_app()
