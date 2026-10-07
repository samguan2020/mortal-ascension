interface Planar { x: number; z: number }

/** Merge keyboard/gamepad input without diagonal speed gain. */
export function direction(keys: Set<string>, padX: number, padZ: number): Planar {
  let x = Number(keys.has("KeyD") || keys.has("ArrowRight")) - Number(keys.has("KeyA") || keys.has("ArrowLeft"));
  let z = Number(keys.has("KeyS") || keys.has("ArrowDown")) - Number(keys.has("KeyW") || keys.has("ArrowUp"));
  if (Math.hypot(padX, padZ) > 0.18) { x += padX; z += padZ; }
  const length = Math.hypot(x, z);
  return length ? { x: x / length, z: z / length } : { x: 0, z: 0 };
}

/** Advance inside the room and report actual distance for animation playback. */
export function advance(position: Planar, input: Planar, delta: number, speed: number, bounds: Planar) {
  const x = Math.max(-bounds.x, Math.min(bounds.x, position.x + input.x * delta * speed));
  const z = Math.max(-bounds.z, Math.min(bounds.z, position.z + input.z * delta * speed));
  return { x, z, distance: Math.hypot(x - position.x, z - position.z) };
}
