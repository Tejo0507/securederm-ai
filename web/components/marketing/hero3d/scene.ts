import * as THREE from "three";
import type { ThemeColors } from "@/lib/useThemeColors";

export type ScenePhase = "training" | "uploading" | "aggregating" | "distributing";
type Token = Exclude<keyof ThemeColors, "dark">;

export interface FederationSceneHandle {
  setColors(colors: ThemeColors): void;
  setPhase(phase: ScenePhase): void;
  /** Render loop on or off (off while the hero is scrolled away). */
  setActive(active: boolean): void;
  /**
   * HTML labels to pin over the scene: one per site in SITES order, then
   * one for the hub. Positioned each frame with a CSS transform.
   */
  setLabels(elements: (HTMLElement | null)[]): void;
  dispose(): void;
}

/** Hospitals sit on a ring around the aggregator, the first nearest the viewer. */
const RING_RADIUS = 2.7;
export const SITES = ["A", "B", "C", "D", "E"].map((id, i, all) => {
  const angle = (i / all.length) * Math.PI * 2 + Math.PI / 2;
  return { id, label: `Hospital ${id}`, x: Math.cos(angle) * RING_RADIUS, z: Math.sin(angle) * RING_RADIUS };
});

const HUB_TOP = new THREE.Vector3(0, 0.5, 0);
const CAMERA_HOME = new THREE.Vector3(0, 5.0, 8.1);
const LOOK_AT = new THREE.Vector3(0, -0.55, 0);

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
  // Roofs light up while a site trains, each a beat after the last.
  const roofMaterial = keep(new THREE.MeshStandardMaterial({ roughness: 0.6, metalness: 0 }));
  const hospitals = SITES.map((site) => {
    const building = new THREE.Group();
    building.position.set(site.x, 0, site.z);
    building.rotation.y = Math.atan2(-site.x, -site.z); // same side faces the hub
    const block = outlined(GEO.block, solid("surface"), edge("ink3"), 0.31);
    block.position.x = 0.08;
    block.position.z = 0.06;
    const wing = outlined(GEO.wing, solid("surface"), edge("ink3"), 0.22);
    wing.position.x = -0.3;
    const ownRoof = keep(roofMaterial.clone());
    const roof = outlined(GEO.roof, ownRoof, edge("ink3"), 0.54);
    roof.position.x = 0.08;
    roof.position.z = 0.06;
    building.add(outlined(GEO.plinth, solid("surface"), edge("lineStrong"), 0.05), block, wing, roof);
    // Local images: a small stack that never leaves the site.
    const slabs = [0, 1, 2].map((i) => {
      const slab = outlined(GEO.slab, solid("sunken"), edge("ink3"), 0.37 + i * 0.045);
      slab.position.x = -0.3;
      slab.position.z = -0.02;
      building.add(slab);
      return slab;
    });
    world.add(building);
    return { roof: ownRoof, slabs };
  });

  // ── Aggregator and the global model above it ──
  const hub = new THREE.Group();
  hub.add(outlined(GEO.hub, solid("ink"), edge("ink2"), 0.21), outlined(GEO.hubCap, solid("ink2"), edge("ink3"), 0.45));
  const model = outlined(GEO.model, solid("accent"), edge("onAccent"), 1.0);
  hub.add(model);
  // FedAvg pulse: a flat ring that swells out from the hub while averaging.
  const haloMaterial = keep(new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false }));
  const halo = new THREE.Mesh(keep(new THREE.RingGeometry(0.72, 0.8, 6)), haloMaterial);
  halo.rotation.x = -Math.PI / 2;
  halo.position.y = 0.02;
  hub.add(halo);
  world.add(hub);

  // ── Update paths, each with a glowing overlay and three update packets ──
  const glowMaterial = keep(new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }));
  const packetMaterial = keep(new THREE.MeshBasicMaterial());
  const packetGeometry = keep(new THREE.BoxGeometry(0.08, 0.08, 0.08));
  const PACKETS_PER_ARC = 3;
  const arcs = SITES.map((site) => {
    const curve = arcFor(site);
    const tube = new THREE.Mesh(keep(new THREE.TubeGeometry(curve, 64, 0.011, 6)), keep(new THREE.MeshBasicMaterial()));
    const glow = new THREE.Mesh(keep(new THREE.TubeGeometry(curve, 64, 0.024, 8)), glowMaterial);
    const packets = Array.from({ length: PACKETS_PER_ARC }, () => {
      const packet = new THREE.Mesh(packetGeometry, packetMaterial);
      packet.visible = false;
      world.add(packet);
      return packet;
    });
    world.add(tube, glow);
    return { curve, tube, packets };
  });

  // ── Round phases: each visual eases toward its target weight. ──
  const TARGETS: Record<ScenePhase, { train: number; up: number; agg: number; down: number }> = {
    training: { train: 1, up: 0, agg: 0, down: 0 },
    uploading: { train: 0, up: 1, agg: 0, down: 0 },
    aggregating: { train: 0, up: 0, agg: 1, down: 0 },
    distributing: { train: 0, up: 0, agg: 0, down: 1 },
  };
  let phase: ScenePhase = "training";
  const weight = { train: 1, up: 0, agg: 0, down: 0 };
  let phaseStart = 0;
  const roofIdle = new THREE.Color();
  const roofLit = new THREE.Color();
  const point = new THREE.Vector3();
  const tangent = new THREE.Vector3();
  const ahead = new THREE.Vector3();
  const easeInOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);

  // Camera and pointer state (wired up below, read every frame).
  let pullBack = 1;
  let dragging = false;
  let spin = 0;
  const pointer = { x: 0, y: 0 };
  const look = { x: 0, y: 0 };
  const lean = new THREE.Vector3();

  // ── Labels: HTML pinned to projected anchor points, dimmed at the back. ──
  let labels: (HTMLElement | null)[] = [];
  // Measured outside the frame loop: reading layout right after writing
  // transforms would force a reflow every frame.
  let labelWidths: number[] = [];
  const measureLabels = () => {
    labelWidths = labels.map((el) => el?.offsetWidth ?? 0);
  };
  const anchors = [
    ...SITES.map((s) => new THREE.Vector3(s.x, 0.78, s.z)),
    // The hub's label sits off its right flank in screen terms (unaffected by
    // the turntable), clear of the model and of the front site's label.
    new THREE.Vector3(0.8, 0.3, 0.2),
  ];
  const projected = new THREE.Vector3();
  function placeLabels() {
    if (!labels.length) return;
    world.updateMatrixWorld();
    camera.updateMatrixWorld();
    const { clientWidth: w, clientHeight: h } = host;
    anchors.forEach((anchor, i) => {
      const el = labels[i];
      if (!el) return;
      const isSite = i < SITES.length;
      projected.copy(anchor);
      if (isSite) projected.applyMatrix4(world.matrixWorld);
      // How far toward the viewer this anchor has turned: -1 back, 1 front.
      const facing = projected.z / RING_RADIUS;
      projected.project(camera);
      let x = (projected.x * 0.5 + 0.5) * w;
      const y = (-projected.y * 0.5 + 0.5) * h;
      // Keep every label wholly inside the stage on narrow screens.
      const width = labelWidths[i] ?? 0;
      const EDGE = 6;
      if (isSite) x = THREE.MathUtils.clamp(x, width / 2 + EDGE, Math.max(width / 2 + EDGE, w - width / 2 - EDGE));
      else x = Math.min(x, Math.max(EDGE, w - width - EDGE));
      // Sites sit centered above their anchor; the hub's label starts at its anchor.
      const offset = isSite ? "translate(-50%, -100%)" : "translate(0, -50%)";
      el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) ${offset}`;
      if (isSite) {
        el.style.opacity = (0.55 + 0.45 * THREE.MathUtils.clamp((facing + 1) / 2, 0, 1)).toFixed(2);
        el.style.zIndex = String(Math.round((facing + 1) * 10));
      }
    });
  }

  function animate(time: number, dt: number) {
    const ease = 1 - Math.exp(-dt * 5);
    const target = TARGETS[phase];
    for (const k of ["train", "up", "agg", "down"] as const) weight[k] += (target[k] - weight[k]) * ease;
    const sincePhase = time - phaseStart;

    // The whole model turns slowly, like a piece on a turntable; a drag adds
    // spin that dies away.
    if (!dragging) {
      world.rotation.y += dt * (0.06 + spin);
      spin *= Math.exp(-dt * 2.2);
    }

    // The camera leans toward the pointer a little.
    look.x += (pointer.x - look.x) * (1 - Math.exp(-dt * 3));
    look.y += (pointer.y - look.y) * (1 - Math.exp(-dt * 3));
    camera.position
      .copy(CAMERA_HOME)
      .multiplyScalar(pullBack)
      .add(lean.set(look.x * 1.1, -look.y * 0.6, 0));
    camera.lookAt(LOOK_AT);
    placeLabels();

    hospitals.forEach((h, i) => {
      const stagger = Math.min(1, Math.max(0, sincePhase * 2.2 - i * 0.18));
      const lit = weight.train * (phase === "training" ? stagger : 1);
      h.roof.color.copy(roofIdle).lerp(roofLit, lit);
      h.roof.emissive.copy(roofLit).multiplyScalar(lit * 0.25);
      h.slabs.forEach((s, j) => {
        s.position.y = 0.37 + j * 0.045 + Math.sin(time * 4 + i + j * 0.9) * 0.012 * lit;
      });
    });

    const moving = Math.max(weight.up, weight.down);
    glowMaterial.opacity = moving * 0.35;
    const outbound = weight.down > weight.up;
    arcs.forEach((arc, i) => {
      arc.packets.forEach((packet, k) => {
        packet.visible = moving > 0.04;
        if (!packet.visible) return;
        const raw = (time * 0.55 + k / PACKETS_PER_ARC + i * 0.07) % 1;
        const t = easeInOut(outbound ? 1 - raw : raw);
        arc.curve.getPoint(t, point);
        arc.curve.getTangent(t, tangent);
        packet.position.copy(point);
        packet.lookAt(ahead.copy(point).add(tangent));
        packet.scale.setScalar(moving * (0.75 + 0.25 * Math.sin(raw * Math.PI)));
      });
    });

    const pulse = (sincePhase * 1.4) % 1;
    halo.scale.setScalar(1 + pulse * 0.9 * weight.agg);
    haloMaterial.opacity = weight.agg * (1 - pulse) * 0.55;
    model.rotation.y += dt * (0.5 + weight.agg * 4);
    model.position.y = 1.0 + Math.sin(time * 1.6) * 0.05 + weight.agg * 0.12;
    model.scale.setScalar(1 + weight.agg * 0.18 * (1 - pulse) + weight.down * 0.06);
  }

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
    roofIdle.set(c.sunken);
    roofLit.set(c.accent);
    glowMaterial.color.set(c.accent);
    packetMaterial.color.set(c.accent);
    haloMaterial.color.set(c.accent);
  }
  applyColors(initial);

  // ── Size: keep the whole ring in frame from wide to portrait. ──
  function resize() {
    const { clientWidth: w, clientHeight: h } = host;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    pullBack = Math.max(1, 1.3 / camera.aspect);
    camera.position.copy(CAMERA_HOME).multiplyScalar(pullBack);
    camera.lookAt(LOOK_AT);
    camera.updateProjectionMatrix();
    measureLabels(); // label text size changes at breakpoints
    placeLabels();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(host);
  resize();

  // ── Pointer: lean toward a hovering mouse; drag sideways to spin. ──
  // Touch keeps vertical panning for the page (touch-action: pan-y), so only
  // a sideways swipe turns the model.
  canvas.style.touchAction = "pan-y";
  canvas.style.cursor = "grab";
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  let dragX = 0;
  let dragVelocity = 0;
  const onMove = (e: PointerEvent) => {
    const rect = canvas.getBoundingClientRect();
    if (finePointer) {
      pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = ((e.clientY - rect.top) / rect.height) * 2 - 1;
    }
    if (!dragging) return;
    const dx = e.clientX - dragX;
    dragX = e.clientX;
    dragVelocity = (dx / rect.width) * Math.PI * 1.5;
    world.rotation.y += dragVelocity;
  };
  const onDown = (e: PointerEvent) => {
    dragging = true;
    dragX = e.clientX;
    dragVelocity = 0;
    canvas.setPointerCapture(e.pointerId);
    canvas.style.cursor = "grabbing";
  };
  const onUp = (e: PointerEvent) => {
    if (!dragging) return;
    dragging = false;
    // Hand the last drag speed (radians per event, ~60 events/s) to the spin.
    spin = THREE.MathUtils.clamp(dragVelocity * 60, -4, 4);
    if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId);
    canvas.style.cursor = "grab";
  };
  const onLeave = () => {
    pointer.x = 0;
    pointer.y = 0;
  };
  canvas.addEventListener("pointermove", onMove);
  canvas.addEventListener("pointerdown", onDown);
  canvas.addEventListener("pointerup", onUp);
  canvas.addEventListener("pointercancel", onUp);
  canvas.addEventListener("pointerleave", onLeave);

  let last = performance.now();
  const frame = (now: number) => {
    // Clamp the step so a frame after a long pause doesn't jump.
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    animate(now / 1000, dt);
    renderer.render(scene, camera);
  };
  let active = false;

  return {
    setColors: applyColors,
    setLabels(elements) {
      labels = elements;
      measureLabels();
      placeLabels();
    },
    setPhase(next) {
      if (next === phase) return;
      phase = next;
      phaseStart = performance.now() / 1000;
      // Called after React rendered the new status text, so widths are current.
      measureLabels();
    },
    setActive(next) {
      if (next === active) return;
      active = next;
      last = performance.now();
      renderer.setAnimationLoop(next ? frame : null);
    },
    dispose() {
      renderer.setAnimationLoop(null);
      ro.disconnect();
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointercancel", onUp);
      canvas.removeEventListener("pointerleave", onLeave);
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
