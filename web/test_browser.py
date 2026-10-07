"""Exercise the independent Vite client with mocked API responses and real skins."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def run(base_url: str, screenshot: Path | None) -> None:
    """Validate controls, poses, framing and failures without making LLM requests."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def instrument(route):
            response = route.fetch()
            body = response.text().replace(
                "let lastFrame = performance.now();",
                "window.probe = { player, npc, camera, T, poses: () => ({ playerPoses, npcPoses }) };"
                "let lastFrame = performance.now();",
            )
            assert "window.probe" in body, "Vite instrumentation marker missing"
            route.fulfill(response=response, body=body)

        page.route("**/src/main.ts*", instrument)
        page.route("**/api/health", lambda route: route.fulfill(json={"status": "healthy"}))
        page.route("**/api/session", lambda route: route.fulfill(json={
            "npc_name": "柳掌柜",
            "messages": [
                {"role": "player", "message": "掌柜，还记得我方才问的事吗？"},
                {"role": "npc", "message": "自然记得，客官问的是栖霞山。"},
            ],
            "memory_turns": 1,
            "max_memory_turns": 8,
        }))
        page.route("**/api/chat", lambda route: route.fulfill(json={
            "success": True,
            "message": "想入仙途，先要心定。东边栖霞山近日来了几位修行人，客官不妨前去探问。",
        }))
        page.goto(base_url, wait_until="networkidle")
        restored_log = page.get_by_text("自然记得，客官问的是栖霞山。", exact=True)
        restored_log.wait_for(state="attached")
        page.wait_for_function("!!window.probe?.poses().playerPoses")
        start = page.evaluate("probe.player.position.x")
        page.keyboard.down("KeyD")
        page.wait_for_function("(start) => probe.player.position.x > start + 1", arg=start)
        assert page.evaluate("probe.poses().playerPoses.active.getClip().name") == "Walk"
        page.keyboard.up("KeyD")
        page.wait_for_function("probe.poses().playerPoses.active.getClip().name === 'Idle'")
        page.evaluate("probe.player.position.set(1, 0, 0.1)")
        page.wait_for_timeout(300)
        page.keyboard.press("KeyE")
        assert page.locator("#conversation").is_visible()
        assert restored_log.is_visible()
        page.locator("#message").fill("怎样修仙？")
        page.locator("#send").click()
        page.wait_for_function("probe.poses().npcPoses.active.getClip().name === 'TalkExplain'")
        hand1 = page.evaluate("""() => {
            let mesh, index;
            probe.npc.traverse(o => {
                if (mesh || !o.isSkinnedMesh) return;
                const bone = o.skeleton.bones.findIndex(
                    b => b.name.replace(/[^a-zA-Z]/g, '') === 'HandR');
                if (bone < 0) return;
                const joints = o.geometry.attributes.skinIndex;
                const weights = o.geometry.attributes.skinWeight;
                for (let i = 0; i < joints.count; i++) {
                    for (let c = 0; c < 4; c++) {
                        if (joints.getComponent(i, c) === bone &&
                            weights.getComponent(i, c) > 0.9) {
                            mesh = o; index = i; return;
                        }
                    }
                }
            });
            if (!mesh) throw Error('No skinned right-hand vertex found');
            window.sampleHand = () => {
                mesh.skeleton.update();
                return mesh.getVertexPosition(index, new probe.T.Vector3()).toArray();
            };
            return sampleHand();
        }""")
        page.wait_for_timeout(700)
        hand2 = page.evaluate("sampleHand()")
        distance = sum((a - b) ** 2 for a, b in zip(hand1, hand2)) ** 0.5
        assert distance > 0.01, f"Hand did not visibly deform: {distance}"
        if screenshot:
            page.screenshot(path=str(screenshot))
        assert page.evaluate("probe.camera.view.enabled")
        page.wait_for_function("probe.poses().npcPoses.active.getClip().name === 'Idle'", timeout=12000)
        page.locator("#message").fill("宗门在哪里？")
        page.locator("#send").click()
        page.wait_for_function("probe.poses().npcPoses.active.getClip().name === 'TalkWelcome'")
        page.locator("#close").click()
        page.wait_for_function("probe.poses().npcPoses.active.getClip().name === 'Idle'")
        assert page.locator("#conversation").is_hidden()
        assert not page.evaluate("probe.camera.view.enabled")
        page.keyboard.press("KeyE")
        page.unroute("**/api/chat")
        page.route("**/api/chat", lambda route: route.fulfill(
            status=503, json={"detail": "unavailable"}))
        page.locator("#message").fill("失败分支")
        page.locator("#send").click()
        page.get_by_text("暂时没能得到回复，请稍后重试。", exact=True).wait_for()
        assert page.evaluate("probe.poses().npcPoses.active.getClip().name") == "Idle"
        page.set_viewport_size({"width": 700, "height": 850})
        page.wait_for_timeout(300)
        assert not page.evaluate("probe.camera.view.enabled")
        assert page.locator("#conversation").bounding_box()["x"] >= 0
        assert not errors, errors
        browser.close()
        print(json.dumps({
            "keyboard_movement": "PASS", "idle_stop": "PASS",
            "proximity_dialogue": "PASS", "both_talk_clips": "PASS",
            "skinned_hand_displacement": round(distance, 4),
            "timeout_and_close": "PASS", "responsive_framing": "PASS",
            "api_error_ui": "PASS", "session_log_restore": "PASS",
            "browser_errors": errors,
        }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5174")
    parser.add_argument("--screenshot", type=Path)
    arguments = parser.parse_args()
    run(arguments.base_url, arguments.screenshot)
