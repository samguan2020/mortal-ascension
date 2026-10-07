import test from "node:test";
import assert from "node:assert/strict";
import { responseMessage, sessionMessages } from "./dialogue.ts";

test("chat response parser accepts only successful nonblank messages", () => {
  assert.equal(responseMessage({ success: true, message: "客官请讲。" }), "客官请讲。");
  assert.equal(responseMessage({ success: false, message: "hidden" }), undefined);
  assert.equal(responseMessage({ success: true, message: "  " }), undefined);
  assert.equal(responseMessage(null), undefined);
});

test("session parser accepts ordered player and npc entries", () => {
  assert.deepEqual(sessionMessages({
    messages: [
      { role: "player", message: "掌柜，请教一事。" },
      { role: "npc", message: "客官但说无妨。" },
    ],
  }), [
    { role: "player", message: "掌柜，请教一事。" },
    { role: "npc", message: "客官但说无妨。" },
  ]);
});

test("session parser rejects malformed entries", () => {
  assert.equal(sessionMessages({ messages: [{ role: "system", message: "hidden" }] }), undefined);
  assert.equal(sessionMessages({ messages: [{ role: "npc", message: "" }] }), undefined);
  assert.equal(sessionMessages({ messages: "not-an-array" }), undefined);
});
