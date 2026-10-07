import { AnimationClip, AnimationMixer, type AnimationAction, type Object3D } from "three/webgpu";

/** A named-clip player shared by actors; simulation decides which pose to select. */
export class PosePlayer {
  private mixer: AnimationMixer;
  private actions = new Map<string, AnimationAction>();
  private active: AnimationAction;

  constructor(root: Object3D, clips: AnimationClip[], required: string[]) {
    this.mixer = new AnimationMixer(root);
    for (const name of required) {
      const clip = AnimationClip.findByName(clips, name);
      if (!clip) throw new Error(`Missing character clip: ${name}`);
      this.actions.set(name, this.mixer.clipAction(clip));
    }
    const idle = this.actions.get("Idle");
    if (!idle) throw new Error("Missing character clip: Idle");
    this.active = idle;
    idle.play();
    this.mixer.update(0);
  }

  /** Select a pose while preserving an already-playing cycle. */
  select(name: string, speed = 1): void {
    const next = this.actions.get(name);
    if (!next) throw new Error(`Unknown character clip: ${name}`);
    if (next !== this.active) {
      next.reset().setEffectiveWeight(1).play();
      this.active.crossFadeTo(next, 0.25, false);
      this.active = next;
    }
    next.setEffectiveTimeScale(speed);
  }

  /** Advance the pose from the simulation clock. */
  tick(delta: number): void {
    this.mixer.update(delta);
  }
}
