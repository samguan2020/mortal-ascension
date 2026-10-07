"""Validate the protected cloud app; --live-chat explicitly permits one LLM call."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright

from tools.deploy_azure import cli

ROOT = Path(__file__).resolve().parents[1]


def verify(args: argparse.Namespace) -> None:
    """Check access boundaries, exact assets, browser rendering and optional live AI."""
    password = cli(
        "containerapp", "secret", "list", "--name", args.app,
        "--resource-group", args.resource_group, "--subscription", args.subscription,
        "--show-values", "--query", "[?name=='site-password'].value | [0]",
    )
    if not isinstance(password, str) or len(password) < 32:
        raise RuntimeError("Azure did not return the expected protected site credential")
    authorization = "Basic " + base64.b64encode(("player:" + password).encode()).decode()

    def request(path, auth=False, method="GET", body=None, origin=None):
        headers = {"Authorization": authorization} if auth else {}
        if origin:
            headers["Origin"] = origin
        if body is not None:
            headers["Content-Type"] = "application/json"
        value = json.dumps(body).encode() if body is not None else None
        req = Request(args.origin + path, method=method, headers=headers, data=value)
        try:
            with urlopen(req, timeout=90) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    assert request("/healthz")[0] == 200
    for path in ("/", "/api/health", "/characters/liu_innkeeper_animated.glb"):
        assert request(path)[0] == 401, f"Anonymous access not rejected: {path}"
    body = {"npc_name": "柳掌柜", "message": "hello"}
    assert request("/api/chat", method="POST", body=body, origin=args.origin)[0] == 401
    assert request("/api/chat", auth=True, method="POST", body=body,
                   origin="https://untrusted.invalid")[0] == 403
    assert request("/api/health", auth=True)[0] == 200
    for path in ("/.env", "/backend/.env"):
        assert request(path, auth=True)[0] == 404
    for name in ("liu_innkeeper_animated.glb", "player_traveler_animated.glb"):
        status, data = request("/characters/" + name, auth=True)
        local = ROOT / "web" / "public" / "characters" / name
        assert status == 200
        assert hashlib.sha256(data).digest() == hashlib.sha256(local.read_bytes()).digest()
    print("PASS: HTTPS, auth boundaries, cross-origin denial, private assets and secret-file denial", flush=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1440, "height": 900},
            http_credentials={"username": "player", "password": password},
        )
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.origin, wait_until="networkidle", timeout=120000)
        page.get_by_text("旅人行走 · 掌柜交谈手势", exact=True).wait_for(timeout=60000)
        page.keyboard.down("KeyD")
        # Software rendering may be slower than real time; match the game's
        # clamped simulation clock instead of assuming a wall-clock framerate.
        page.evaluate("""() => new Promise(resolve => {
            let elapsed = 0;
            let previous = performance.now();
            function frame(now) {
                elapsed += Math.min((now - previous) / 1000, 0.05);
                previous = now;
                if (elapsed >= 1.15) resolve();
                else requestAnimationFrame(frame);
            }
            requestAnimationFrame(frame);
        })""")
        page.keyboard.up("KeyD")
        page.keyboard.down("KeyW")
        page.locator("#interact").wait_for(state="visible", timeout=20000)
        page.keyboard.up("KeyW")
        page.keyboard.press("KeyE")
        assert page.locator("#conversation").is_visible()
        reply_length = 0
        if args.live_chat:
            page.locator("#message").fill("柳掌柜你好，初来青石镇，想打听附近仙门，请简短指条路。")
            with page.expect_response(lambda response: response.url.endswith("/api/chat"), timeout=45000) as pending:
                page.locator("#send").click()
            reply = pending.value
            payload = reply.json()
            if reply.status != 200:
                code = payload.get("error", {}).get("code", "unknown")
                raise RuntimeError(f"Live chat failed: HTTP {reply.status}, code={code}")
            assert payload.get("success") is True
            reply_length = len(payload.get("message", "").strip())
            assert reply_length > 5
            assert page.locator(".from-npc").count() == 2
            session = next(cookie for cookie in page.context.cookies()
                           if cookie["name"] == "__Host-ai-town-session")
            assert session["secure"] and session["httpOnly"] and session["sameSite"] == "Strict"
            page.wait_for_timeout(650)
        if args.screenshot:
            page.screenshot(path=str(args.screenshot))
        assert not errors, errors
        print(json.dumps({
            "cloud_browser": "PASS",
            "renderer": page.locator("#renderer-state").inner_text(),
            "real_llm_requests": int(args.live_chat),
            "response_characters": reply_length,
            "page_errors": errors,
        }), flush=True)
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--app", default="tingyu-inn")
    parser.add_argument("--resource-group", default="rg-ai-town")
    parser.add_argument("--live-chat", action="store_true")
    parser.add_argument("--screenshot", type=Path)
    verify(parser.parse_args())
