// PROTOTYPE - NOT FOR PRODUCTION
// Question: Does movement, not elapsed time alone, drive player walking?
// Date: 2026-10-06

import assert from "node:assert/strict";
import test from "node:test";
import { AnimationClip, Group, NumberKeyframeTrack } from "three/webgpu";
import { NpcConversationMotion, PlayerLocomotion } from "../src/character-motion.ts";

function fixture() {
  const model = new Group();
  const clips = [
    new AnimationClip("Idle", 1, [new NumberKeyframeTrack(".rotation[x]", [0, 1], [0, 0])]),
    new AnimationClip("Walk", 1, [new NumberKeyframeTrack(".rotation[x]", [0, 0.5, 1], [0, 0.4, 0])]),
  ];
  return { model, clips, controller: new PlayerLocomotion(model, clips) };
}

test("starts standing; movement crossfades into walk", () => {
  const { controller, model, clips } = fixture();
  controller.update(0.25, 0);
  assert.equal(model.rotation.x, 0);
  controller.update(0.25, 2.8);
  controller.update(0.10, 2.8);
  assert.ok(model.rotation.x > 0.1);
  assert.equal(controller.mixer.clipAction(clips[1]).getEffectiveWeight(), 1);
});

test("stopping, dialogue or a blocked boundary fades back to idle", () => {
  const { controller, model, clips } = fixture();
  controller.update(0.3, 4.2);
  controller.update(0.3, 0);
  controller.update(0.3, 0);
  assert.equal(model.rotation.x, 0);
  assert.equal(controller.mixer.clipAction(clips[1]).getEffectiveWeight(), 0);
});

test("walk cadence follows actual movement speed and resumes after stopping", () => {
  const { controller, clips } = fixture();
  controller.update(0.1, 4.2);
  assert.ok(Math.abs(controller.mixer.clipAction(clips[1]).getEffectiveTimeScale() - 1.5) < 1e-6);
  controller.update(0.4, 0);
  controller.update(0.2, 2.8);
  controller.update(0.1, 2.8);
  assert.equal(controller.mixer.clipAction(clips[1]).getEffectiveWeight(), 1);
  assert.equal(controller.mixer.clipAction(clips[1]).getEffectiveTimeScale(), 1);
});

test("missing clips and invalid controller input fail explicitly", () => {
  assert.throws(() => new PlayerLocomotion(new Group(), []), /Idle and Walk/);
  const { controller } = fixture();
  assert.throws(() => controller.update(NaN, 1), RangeError);
  assert.throws(() => controller.update(0.1, -1), RangeError);
});

function npcFixture() {
  const model = new Group();
  const clips = [
    new AnimationClip("Idle", 1, [new NumberKeyframeTrack(".rotation[x]", [0, 1], [0, 0])]),
    new AnimationClip("TalkExplain", 2, [new NumberKeyframeTrack(".rotation[x]", [0, 1, 2], [0, 0.6, 0])]),
    new AnimationClip("TalkWelcome", 2, [new NumberKeyframeTrack(".rotation[x]", [0, 1, 2], [0, -0.6, 0])]),
  ];
  return { model, clips, controller: new NpcConversationMotion(model, clips) };
}

test("NPC stays idle until a reply explicitly starts a gesture", () => {
  const { model, controller } = npcFixture();
  controller.update(0.5, false);
  assert.equal(model.rotation.x, 0);
  controller.update(0.5, true);
  assert.equal(model.rotation.x, 0);
  controller.speak();
  controller.update(0.5, true);
  assert.ok(model.rotation.x > 0.1);
});

test("NPC alternates gestures, including replies arriving during a previous gesture", () => {
  const { model, controller } = npcFixture();
  controller.speak();
  controller.update(0.5, true);
  assert.ok(model.rotation.x > 0);
  controller.speak();
  controller.update(0.5, true);
  assert.ok(model.rotation.x < 0);
  controller.speak();
  controller.update(0.5, true);
  assert.ok(model.rotation.x > 0);
});

test("NPC fades to idle at reply timeout or dialogue close", () => {
  const { model, clips, controller } = npcFixture();
  controller.speak();
  controller.update(0.5, true);
  controller.update(0.4, false);
  controller.update(0.4, false);
  assert.equal(model.rotation.x, 0);
  assert.equal(controller.mixer.clipAction(clips[1]).getEffectiveWeight(), 0);
});

test("NPC requires both gestures and valid time", () => {
  assert.throws(() => new NpcConversationMotion(new Group(), []), /requires Idle/);
  const { controller, clips } = npcFixture();
  assert.throws(() => new NpcConversationMotion(new Group(), clips.slice(0, 2)), /TalkWelcome/);
  assert.throws(() => controller.update(NaN, false), RangeError);
});
