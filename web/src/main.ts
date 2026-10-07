import * as T from "three/webgpu";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { PosePlayer } from "./actors.ts";
import { world, text } from "./config.ts";
import { responseMessage, sessionMessages } from "./dialogue.ts";
import { direction, advance } from "./movement.ts";
import { furnish, label } from "./scene.ts";
import "./style.css";

function element<E extends HTMLElement>(id: string, kind: { new(): E }): E {
  const found = document.getElementById(id);
  if (!(found instanceof kind)) throw new Error(`Missing interface element: ${id}`);
  return found;
}

const panel = element("conversation", HTMLElement);
const input = element("message", HTMLInputElement);
const send = element("send", HTMLButtonElement);
const close = element("close", HTMLButtonElement);
const interact = element("interact", HTMLButtonElement);
const chatStatus = element("chat-status", HTMLElement);
const notice = element("notice", HTMLElement);

function announce(message: string): void {
  notice.textContent = message;
  notice.hidden = false;
}

function appendMessage(value: string, player = false): void {
  const row = document.createElement("p");
  row.className = player ? "from-player" : "from-npc";
  row.textContent = value;
  const log = element("messages", HTMLElement);
  log.append(row);
  log.scrollTop = log.scrollHeight;
}

async function loadActor(parent: T.Group, url: string, names: string[]): Promise<PosePlayer> {
  const asset = await new GLTFLoader().loadAsync(url);
  const model = asset.scene;
  model.updateMatrixWorld(true);
  const box = new T.Box3().setFromObject(model);
  const height = box.max.y - box.min.y;
  if (!Number.isFinite(height) || height <= 0) throw new Error("Invalid character geometry");
  model.scale.setScalar(world.actorHeight / height);
  model.updateMatrixWorld(true);
  box.setFromObject(model);
  const center = box.getCenter(new T.Vector3());
  model.position.set(-center.x, -box.min.y, -center.z);
  let hasSkin = false;
  model.traverse((part) => {
    if (part instanceof T.Mesh) { part.castShadow = true; part.receiveShadow = true; }
    if (part instanceof T.SkinnedMesh) hasSkin = true;
  });
  if (!hasSkin) throw new Error("Character is missing its skin");
  const poses = new PosePlayer(model, asset.animations, names);
  parent.add(model);
  return poses;
}

async function boot(): Promise<void> {
  const viewport = element("viewport", HTMLDivElement);
  const scene = new T.Scene();
  scene.background = new T.Color(world.palette.sky);
  scene.fog = new T.Fog(world.palette.mist, 24, 65);
  const camera = new T.PerspectiveCamera(38, innerWidth / innerHeight, 0.1, 100);
  const renderer = new T.WebGPURenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75));
  renderer.setSize(innerWidth, innerHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = T.PCFSoftShadowMap;
  renderer.toneMapping = T.AgXToneMapping;
  renderer.toneMappingExposure = 1.12;
  await renderer.init();
  renderer.domElement.tabIndex = 0;
  renderer.domElement.setAttribute("aria-label", "游戏场景，使用方向键移动");
  viewport.append(renderer.domElement);
  const gpu = renderer.backend.constructor.name.toLowerCase().includes("webgpu");
  element("renderer-state", HTMLElement).textContent = gpu ? text.gpu : text.gl;
  scene.add(new T.HemisphereLight(0xd9f1ff, 0x536e62, 1.75));
  const keyLight = new T.DirectionalLight(0xfff3dc, 2.55);
  keyLight.position.set(8, 12, 5);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  keyLight.shadow.normalBias = 0.035;
  keyLight.shadow.bias = -0.00015;
  keyLight.shadow.camera.left = -12;
  keyLight.shadow.camera.right = 12;
  keyLight.shadow.camera.top = 12;
  keyLight.shadow.camera.bottom = -12;
  scene.add(keyLight);
  furnish(scene);

  const player = new T.Group();
  player.position.set(...world.playerStart);
  const npc = new T.Group();
  npc.position.set(...world.npcStart);
  npc.rotation.y = -0.45;
  scene.add(player, npc);
  const nameplate = label(world.npcName);
  nameplate.position.copy(npc.position).add(new T.Vector3(0, 3.0, 0));
  nameplate.scale.set(1.8, 0.5, 1);
  scene.add(nameplate);
  const ring = new T.Mesh(new T.RingGeometry(world.interactionRange - 0.045, world.interactionRange, 64),
    new T.MeshBasicMaterial({ color: 0xffd28f, side: T.DoubleSide, transparent: true, opacity: 0.45 }));
  ring.rotation.x = -Math.PI / 2;
  ring.position.copy(npc.position);
  ring.position.y = 0.04;
  ring.visible = false;
  scene.add(ring);
  camera.position.copy(player.position).add(new T.Vector3(...world.cameraOffset));
  camera.lookAt(player.position.x, 0.9, player.position.z);

  let playerPoses: PosePlayer | undefined;
  let npcPoses: PosePlayer | undefined;
  let talking = false;
  let busy = false;
  let gestureUntil = 0;
  let gestureIndex = 0;
  let heldA = false;
  let heldB = false;
  const keys = new Set<string>();
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const near = () => player.position.distanceTo(npc.position) <= world.interactionRange;

  function layout(): void {
    camera.aspect = innerWidth / innerHeight;
    if (talking && innerWidth >= 960) {
      const covered = innerWidth - panel.getBoundingClientRect().left;
      camera.setViewOffset(innerWidth, innerHeight, covered / 2, 0, innerWidth, innerHeight);
    } else camera.clearViewOffset();
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  }

  function showConversation(show: boolean): void {
    if (busy || show && !near()) return;
    talking = show;
    panel.hidden = !show;
    interact.hidden = show || !near();
    keys.clear();
    if (show) {
      npc.lookAt(player.position.x, 0, player.position.z);
      input.focus();
    } else {
      gestureUntil = 0;
      renderer.domElement.focus();
    }
    layout();
  }

  close.addEventListener("click", () => showConversation(false));
  interact.addEventListener("click", () => showConversation(true));
  window.addEventListener("resize", layout);
  window.addEventListener("blur", () => keys.clear());
  document.addEventListener("visibilitychange", () => keys.clear());
  window.addEventListener("keydown", (event) => {
    if (event.code === "Escape") { showConversation(false); return; }
    if (talking || event.target instanceof HTMLInputElement || event.repeat) return;
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(event.code)) event.preventDefault();
    keys.add(event.code);
    if (event.code === "KeyE") showConversation(true);
  });
  window.addEventListener("keyup", (event) => keys.delete(event.code));
  document.querySelectorAll<HTMLButtonElement>("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => { input.value = button.dataset.prompt ?? ""; input.focus(); });
  });
  appendMessage(text.greeting);
  input.disabled = send.disabled = true;
  void fetch("/api/session", { signal: AbortSignal.timeout(20000) }).then(async (response) => {
    if (!response.ok) throw new Error(`Session HTTP ${response.status}`);
    const restored = sessionMessages(await response.json());
    if (!restored) throw new Error("Invalid session response");
    if (restored.length) {
      element("messages", HTMLElement).replaceChildren();
      for (const entry of restored) appendMessage(entry.message, entry.role === "player");
    }
  }).catch((error: unknown) => {
    console.error("Dialogue session recovery failed", error);
  }).finally(() => {
    input.disabled = send.disabled = false;
  });
  element("chat-form", HTMLFormElement).addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question || busy) return;
    busy = true;
    send.disabled = input.disabled = close.disabled = true;
    appendMessage(question, true);
    input.value = "";
    chatStatus.textContent = text.thinking;
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ npc_name: world.npcName, message: question }),
        signal: AbortSignal.timeout(40000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const reply = responseMessage(await response.json());
      if (!reply) throw new Error("Invalid chat response");
      appendMessage(reply);
      npcPoses?.select(gestureIndex++ % 2 ? "TalkWelcome" : "TalkExplain");
      gestureUntil = performance.now() + Math.min(8000, Math.max(3500, reply.length * 55));
      chatStatus.textContent = "";
    } catch (error) {
      console.error("Conversation request failed", error);
      chatStatus.textContent = text.failed;
    } finally {
      busy = false;
      send.disabled = input.disabled = close.disabled = false;
      input.focus();
    }
  });

  void fetch("/api/health", { signal: AbortSignal.timeout(20000) }).then((response) => {
    if (!response.ok) throw new Error(`Health HTTP ${response.status}`);
    element("api-state", HTMLElement).textContent = text.online;
  }).catch((error: unknown) => {
    console.error("API health check failed", error);
    element("api-state", HTMLElement).textContent = text.offline;
    announce(text.offline);
  });
  void Promise.all([
    loadActor(player, world.playerAsset, ["Idle", "Walk"]),
    loadActor(npc, world.npcAsset, ["Idle", "TalkExplain", "TalkWelcome"]),
  ]).then(([hero, innkeeper]) => {
    playerPoses = hero;
    npcPoses = innkeeper;
    element("actor-state", HTMLElement).textContent = text.actors;
  }).catch((error: unknown) => {
    console.error("Character assets failed", error);
    element("actor-state", HTMLElement).textContent = "人物加载失败";
    announce(text.initFailed);
  });

  let lastFrame = performance.now();
  renderer.setAnimationLoop(() => {
    const now = performance.now();
    const delta = Math.min((now - lastFrame) / 1000, 0.05);
    lastFrame = now;
    const pad = navigator.getGamepads?.().find((candidate) => candidate?.connected);
    const a = Boolean(pad?.buttons[0]?.pressed);
    const b = Boolean(pad?.buttons[1]?.pressed);
    if (a && !heldA && !talking) showConversation(true);
    if (b && !heldB && talking) showConversation(false);
    heldA = a; heldB = b;
    const vector = talking ? { x: 0, z: 0 } : direction(keys, pad?.axes[0] ?? 0, pad?.axes[1] ?? 0);
    const step = advance(player.position, vector, delta, world.speed, world.bounds);
    player.position.x = step.x;
    player.position.z = step.z;
    if (step.distance > 0) player.rotation.y = Math.atan2(vector.x, vector.z);
    const moving = step.distance > 0.00001 && !reducedMotion.matches;
    playerPoses?.select(moving ? "Walk" : "Idle", moving && delta > 0 ? step.distance / delta / 2.8 : 1);
    if (!talking || now >= gestureUntil || reducedMotion.matches) npcPoses?.select("Idle");
    playerPoses?.tick(delta);
    npcPoses?.tick(delta);
    interact.hidden = talking || !near();
    ring.visible = !talking && near();
    const goal = player.position.clone().add(new T.Vector3(...world.cameraOffset));
    camera.position.lerp(goal, 1 - Math.exp(-4.5 * delta));
    camera.lookAt(player.position.x, 0.9, player.position.z);
    renderer.render(scene, camera);
  });
}

void boot().catch((error: unknown) => {
  console.error("Game initialization failed", error);
  announce(text.initFailed);
});
