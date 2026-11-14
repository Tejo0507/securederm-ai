import * as THREE from "three";
import type { ThemeColors } from "@/lib/useThemeColors";

export type ScenePhase = "training" | "uploading" | "aggregating" | "distributing";
type Token = Exclude<keyof ThemeColors, "dark">;

export interface FederationSceneHandle {
  setColors(colors: ThemeColors): void;
  setPhase(phase: ScenePhase): void;
  /** Render loop on or off (off while the hero is scrolled away). */
  setActive(active: boolean): void;
  dispose(): void;
}

/** Hospitals sit on a ring around the aggregator, the first nearest the viewer. */
const RING_RADIUS = 2.7;
export const SITES = ["A", "B", "C", "D", "E"].map((id, i, all) => {
  const angle = (i / all.length) * Math.PI * 2 + Math.PI / 2;
  return { id, label: `Hospital ${id}`, x: Math.cos(angle) * RING_RADIUS, z: Math.sin(angle) * RING_RADIUS };
});

const HUB_TOP = new THREE.Vector3(0, 0.5, 0);
const CAMERA_HOME = new THREE.Vector3(0, 5.3, 8.6);
const LOOK_AT = new THREE.Vector3(0, 0.25, 0);

/** The path an update takes: up out of the hospital, over, and down into the hub. */
function arcFor(site: { x: number; z: number }) {
  return new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(site.x, 0.46, site.z),
    new THREE.Vector3(site.x * 0.45, 1.85, site.z * 0.45),
    HUB_TOP,
  );
}

export function createFederationScene(host: HTMLElement, initial: ThemeColors): FederationSceneHandle {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setClearColor(0x000000, 0);
  const canvas = renderer.domElement;
  canvas.setAttribute("aria-hidden", "true");
  canvas.style.display = "block";
  canvas.style.width = "100%";
  canvas.style.height = "100%";
  host.appendChild(canvas);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 60);
  camera.position.copy(CAMERA_HOME);
  camera.lookAt(LOOK_AT);

  // ── Palette: one shared material per design token, recolored in place. ──
  const solids = new Map<Token, THREE.MeshStandardMaterial>();
  const edges = new Map<Token, THREE.LineBasicMaterial>();
  const solid = (token: Token) => {
    let m = solids.get(token);
    if (!m) solids.set(token, (m = new THREE.MeshStandardMaterial({ roughness: 0.85, metalness: 0 })));
    return m;
  };
  const edge = (token: Token) => {
    let m = edges.get(token);
    if (!m) edges.set(token, (m = new THREE.LineBasicMaterial()));
    return m;
  };

  const disposables: { dispose(): void }[] = [];
  const keep = <T extends { dispose(): void }>(thing: T) => {
    disposables.push(thing);
    return thing;
  };

  /** A solid with crisp edge lines: the look of an architect's white model. */
  function outlined(geometry: THREE.BufferGeometry, fill: THREE.Material, line: THREE.Material, y = 0) {
    const group = new THREE.Group();
    const mesh = new THREE.Mesh(geometry, fill);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    group.add(mesh, new THREE.LineSegments(keep(new THREE.EdgesGeometry(geometry, 20)), line));
    group.position.y = y;
    return group;
  }

  const GEO = {
    plinth: keep(new THREE.BoxGeometry(1.0, 0.1, 1.0)),
    block: keep(new THREE.BoxGeometry(0.62, 0.42, 0.46)),
    wing: keep(new THREE.BoxGeometry(0.3, 0.24, 0.5)),
    roof: keep(new THREE.BoxGeometry(0.64, 0.04, 0.48)),
    slab: keep(new THREE.BoxGeometry(0.24, 0.035, 0.24)),
    hub: keep(new THREE.CylinderGeometry(0.6, 0.68, 0.42, 6)),
    hubCap: keep(new THREE.CylinderGeometry(0.46, 0.46, 0.06, 6)),
    model: keep(new THREE.OctahedronGeometry(0.26, 0)),
  };

  const world = new THREE.Group();
  scene.add(world);

  // ── Lights ──
  const hemi = new THREE.HemisphereLight();
  const sun = new THREE.DirectionalLight();
  sun.position.set(-4, 7, 3);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  Object.assign(sun.shadow.camera, { left: -5, right: 5, top: 5, bottom: -5 });
  sun.shadow.radius = 4;
  scene.add(hemi, sun);

  // ── Floor: a polar grid and a catcher for soft shadows. ──
  const grid = new THREE.PolarGridHelper(4.4, 10, 5, 72);
  const gridMaterial = grid.material as THREE.LineBasicMaterial;
  gridMaterial.vertexColors = false;
  grid.position.y = 0.001;
  const shadowMaterial = keep(new THREE.ShadowMaterial({ transparent: true }));
  const floor = new THREE.Mesh(keep(new THREE.CircleGeometry(4.4, 72)), shadowMaterial);
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  world.add(grid, floor);

  // ── Hospitals ──
  for (const site of SITES) {
    const building = new THREE.Group();
    building.position.set(site.x, 0, site.z);
    building.rotation.y = Math.atan2(-site.x, -site.z); // same side faces the hub
    const block = outlined(GEO.block, solid("surface"), edge("ink3"), 0.31);
    block.position.x = 0.08;
    block.position.z = 0.06;
    const wing = outlined(GEO.wing, solid("surface"), edge("ink3"), 0.22);
    wing.position.x = -0.3;
    const roof = outlined(GEO.roof, solid("sunken"), edge("ink3"), 0.54);
    roof.position.x = 0.08;
    roof.position.z = 0.06;
    building.add(outlined(GEO.plinth, solid("surface"), edge("lineStrong"), 0.05), block, wing, roof);
    // Local images: a small stack that never leaves the site.
    for (let i = 0; i < 3; i++) {
      const slab = outlined(GEO.slab, solid("sunken"), edge("ink3"), 0.37 + i * 0.045);
      slab.position.x = -0.3;
      slab.position.z = -0.02;
      building.add(slab);
    }
    world.add(building);
  }

  // ── Aggregator and the global model above it ──
  const hub = new THREE.Group();
  hub.add(outlined(GEO.hub, solid("ink"), edge("ink2"), 0.21), outlined(GEO.hubCap, solid("ink2"), edge("ink3"), 0.45));
  const model = outlined(GEO.model, solid("accent"), edge("onAccent"), 1.05);
  hub.add(model);
  world.add(hub);

  // ── Update paths ──
  const arcs = SITES.map((site) => {
    const curve = arcFor(site);
    const tube = new THREE.Mesh(keep(new THREE.TubeGeometry(curve, 64, 0.011, 6)), keep(new THREE.MeshBasicMaterial()));
    world.add(tube);
    return { curve, tube };
  });

  // ── Theme ──
  function applyColors(c: ThemeColors) {
    solids.forEach((m, token) => m.color.set(c[token]));
    edges.forEach((m, token) => m.color.set(c[token]));
    hemi.color.set(c.surface);
    hemi.groundColor.set(c.sunken);
    hemi.intensity = c.dark ? 0.9 : 1.6;
    sun.intensity = c.dark ? 1.4 : 1.9;
    gridMaterial.color.set(c.line);
    shadowMaterial.opacity = c.dark ? 0.35 : 0.08;
    for (const { tube } of arcs) (tube.material as THREE.MeshBasicMaterial).color.set(c.lineStrong);
  }
  applyColors(initial);

  // ── Size: keep the whole ring in frame from wide to portrait. ──
  function resize() {
    const { clientWidth: w, clientHeight: h } = host;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    const pullBack = Math.max(1, 1.3 / camera.aspect);
    camera.position.copy(CAMERA_HOME).multiplyScalar(pullBack);
    camera.lookAt(LOOK_AT);
    camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(host);
  resize();

  const frame = () => renderer.render(scene, camera);
  let active = false;

  return {
    setColors: applyColors,
    setPhase: () => {},
    setActive(next) {
      if (next === active) return;
      active = next;
      renderer.setAnimationLoop(next ? frame : null);
    },
    dispose() {
      renderer.setAnimationLoop(null);
      ro.disconnect();
      disposables.forEach((d) => d.dispose());
      solids.forEach((m) => m.dispose());
      edges.forEach((m) => m.dispose());
      grid.geometry.dispose();
      gridMaterial.dispose();
      renderer.dispose();
      canvas.remove();
    },
  };
}
