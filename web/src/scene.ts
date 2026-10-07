import * as T from "three/webgpu";
import { world } from "./config.ts";

/** Build the release client's room from its palette and independent geometry. */
export function furnish(scene: T.Scene): void {
  const p = world.palette;
  const material = (color: number, roughness = 0.92) => new T.MeshStandardMaterial({ color, roughness });
  const wood = material(p.beams);
  const plaster = material(p.plaster);
  const boards = material(p.boards);
  const table = material(p.table);
  const jar = material(p.teal, 0.62);
  function box(size: [number, number, number], at: [number, number, number], surface: T.Material) {
    const mesh = new T.Mesh(new T.BoxGeometry(...size), surface);
    mesh.position.set(...at);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    scene.add(mesh);
    return mesh;
  }
  box([18, 0.3, 14], [0, -0.19, 0], wood);
  for (let i = 0; i < 19; i++) box([17.7, 0.035, 0.65], [0, -0.025, -6.5 + i * 0.72], boards);
  box([18, 3.8, 0.25], [0, 1.8, -7], plaster);
  box([0.25, 3.8, 14], [-9, 1.8, 0], plaster);
  for (const x of [-8.6, -5.7, -2.8, 0.1, 3, 5.9, 8.6]) box([0.2, 3.8, 0.4], [x, 1.8, -6.8], wood);
  box([18, 0.24, 0.42], [0, 3.6, -6.8], wood);
  const paper = new T.MeshStandardMaterial({ color: p.paper, emissive: 0x529fa8, emissiveIntensity: 0.3 });
  for (const x of [-5.6, -2.7]) {
    box([2.45, 1.9, 0.13], [x, 2.1, -6.74], wood);
    box([2.22, 1.66, 0.03], [x, 2.1, -6.65], paper);
    for (const dx of [-0.72, 0, 0.72]) box([0.055, 1.7, 0.06], [x + dx, 2.1, -6.60], wood);
    box([2.2, 0.055, 0.06], [x, 2.1, -6.60], wood);
  }
  for (const [x, z] of [[-5, -3.6], [-5, 0.5], [5, 3.6]]) {
    box([2.3, 0.16, 1.35], [x, 1.0, z], table);
    for (const dx of [-0.95, 0.95]) for (const dz of [-0.45, 0.45]) {
      box([0.13, 0.9, 0.13], [x + dx, 0.5, z + dz], wood);
    }
    box([1.8, 0.12, 0.34], [x, 0.48, z + 1.0], table);
    for (const dx of [-0.65, 0.65]) box([0.12, 0.42, 0.23], [x + dx, 0.22, z + 1.0], wood);
  }
  box([5.3, 1.35, 1.15], [3.4, 0.69, -4.8], wood);
  box([5.5, 0.1, 1.3], [3.4, 1.42, -4.8], table);
  box([5, 2.65, 0.25], [3.4, 1.35, -6.70], wood);
  for (const height of [0.7, 1.5, 2.3]) box([5, 0.09, 0.8], [3.4, height, -6.3], table);
  for (let i = 0; i < 6; i++) {
    const vessel = new T.Mesh(new T.SphereGeometry(0.26, 18, 12), jar);
    vessel.scale.y = 1.35;
    vessel.position.set(1.6 + i % 3 * 1.6, i < 3 ? 1.90 : 1.10, -6.22);
    vessel.castShadow = true;
    scene.add(vessel);
  }
  box([5.2, 0.025, 4.2], [2.4, 0.003, -0.9], material(p.red));
  for (const x of [-5.9, 6]) {
    const light = new T.PointLight(0xffbb73, 4, 8, 1.8);
    light.position.set(x, 2.9, -4.9);
    scene.add(light);
    const lantern = new T.Mesh(new T.CylinderGeometry(0.24, 0.32, 0.58, 16),
      new T.MeshStandardMaterial({ color: 0xed673b, emissive: 0xc6441b, emissiveIntensity: 0.8 }));
    lantern.position.copy(light.position);
    scene.add(lantern);
  }
  const title = label("听雨", "#ffe4ab", "#633b2b");
  title.position.set(-0.1, 2.7, -6.48);
  title.scale.set(2.4, 0.8, 1);
  scene.add(title);
  const hills = landscape();
  const backdrop = new T.Mesh(new T.PlaneGeometry(34, 14), new T.MeshBasicMaterial({ map: hills }));
  backdrop.position.set(0, 4.7, -10.5);
  scene.add(backdrop);
  const painting = new T.Mesh(new T.PlaneGeometry(8, 2.5), new T.MeshStandardMaterial({ map: hills, roughness: 1 }));
  painting.position.set(-8.84, 1.95, -0.5);
  painting.rotation.y = Math.PI / 2;
  scene.add(painting);
}

/** Create a readable in-world label without external fonts or image requests. */
export function label(value: string, color = "#fff5d9", background = "#1b5860"): T.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 144;
  const pen = canvas.getContext("2d");
  if (!pen) throw new Error("Canvas text rendering unavailable");
  pen.fillStyle = background;
  pen.fillRect(0, 0, 512, 144);
  pen.strokeStyle = "#dda968";
  pen.lineWidth = 6;
  pen.strokeRect(5, 5, 502, 134);
  pen.fillStyle = color;
  pen.font = "bold 72px serif";
  pen.textAlign = "center";
  pen.textBaseline = "middle";
  pen.fillText(value, 256, 72);
  const texture = new T.CanvasTexture(canvas);
  texture.colorSpace = T.SRGBColorSpace;
  return new T.Sprite(new T.SpriteMaterial({ map: texture, depthTest: false }));
}

function landscape(): T.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 512;
  const pen = canvas.getContext("2d");
  if (!pen) throw new Error("Canvas landscape rendering unavailable");
  const sky = pen.createLinearGradient(0, 0, 0, 512);
  sky.addColorStop(0, "#b4dfec");
  sky.addColorStop(1, "#d5ecd9");
  pen.fillStyle = sky;
  pen.fillRect(0, 0, 1024, 512);
  ["#87b6b4", "#569b9a", "#287574"].forEach((color, layer) => {
    pen.fillStyle = color;
    pen.beginPath();
    pen.moveTo(0, 512);
    for (let x = 0; x <= 1024; x += 8) {
      const y = 290 + layer * 70 - Math.sin(x * 0.008 + layer) * 65 - Math.sin(x * 0.022) * 24;
      pen.lineTo(x, y);
    }
    pen.lineTo(1024, 512);
    pen.fill();
  });
  const texture = new T.CanvasTexture(canvas);
  texture.colorSpace = T.SRGBColorSpace;
  return texture;
}
