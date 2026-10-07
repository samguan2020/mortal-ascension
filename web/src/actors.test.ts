import test from "node:test";
import assert from "node:assert/strict";
import { AnimationClip, Group, NumberKeyframeTrack } from "three/webgpu";
import { PosePlayer } from "./actors.ts";

const clips = () => [
  new AnimationClip("Idle", 1, [new NumberKeyframeTrack(".rotation[x]", [0, 1], [0, 0])]),
  new AnimationClip("Walk", 1, [new NumberKeyframeTrack(".rotation[x]", [0, 0.5, 1], [0, 0.5, 0])]),
];

test("pose player crossfades and settles when idle is selected", () => {
  const group = new Group();
  const player = new PosePlayer(group, clips(), ["Idle", "Walk"]);
  player.select("Walk");
  player.tick(0.3);
  assert.ok(group.rotation.x > 0);
  player.select("Idle");
  player.tick(0.3);
  assert.equal(group.rotation.x, 0);
});

test("missing assets or unknown pose names fail explicitly", () => {
  assert.throws(() => new PosePlayer(new Group(), clips(), ["Talk"]), /Missing/);
  const player = new PosePlayer(new Group(), clips(), ["Idle"]);
  assert.throws(() => player.select("Talk"), /Unknown/);
});
