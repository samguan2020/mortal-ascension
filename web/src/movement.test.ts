import test from "node:test";
import assert from "node:assert/strict";
import { advance, direction } from "./movement.ts";

test("diagonal input is normalized and respects frame time", () => {
  const input = direction(new Set(["KeyD", "KeyW"]), 0, 0);
  assert.ok(Math.abs(Math.hypot(input.x, input.z) - 1) < 1e-9);
  const result = advance({ x: 0, z: 0 }, input, 1, 4, { x: 8, z: 6 });
  assert.ok(Math.abs(result.distance - 4) < 1e-9);
});

test("world bounds stop movement and cancelled keys produce zero input", () => {
  const result = advance({ x: 8, z: 6 }, { x: 1, z: 0 }, 1, 4, { x: 8, z: 6 });
  assert.equal(result.distance, 0);
  assert.deepEqual(direction(new Set(["KeyA", "KeyD"]), 0, 0), { x: 0, z: 0 });
});

test("gamepad has a dead zone and never exceeds unit movement", () => {
  assert.deepEqual(direction(new Set(), 0.1, -0.1), { x: 0, z: 0 });
  const result = direction(new Set(["KeyD"]), 1, 1);
  assert.ok(Math.abs(Math.hypot(result.x, result.z) - 1) < 1e-9);
});
