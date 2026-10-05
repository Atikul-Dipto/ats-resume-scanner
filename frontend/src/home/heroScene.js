// The landing page's 3D scene. Plain three.js (no react-three-fiber) so the
// whole thing is one lazily-loaded chunk with an explicit lifecycle:
// build -> animate (only while visible) -> dispose everything on unmount.

const SKILLS = ["Python", "SQL", "Power BI", "Excel"];

function cssVar(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function palette() {
  const dark = document.documentElement.dataset.theme === "dark";
  return {
    dark,
    primary: cssVar("--primary", "#5b5bf6"),
    primary2: cssVar("--primary-2", "#8b5cf6"),
    good: cssVar("--good", "#0f9f6e"),
    card: dark ? "#161a33" : "#ffffff",
    cardEdge: dark ? "rgba(139,139,255,0.35)" : "rgba(91,91,246,0.18)",
    ink: dark ? "#f4f5ff" : "#0f1536",
    muted: dark ? "#8a92b8" : "#6c7393",
    line: dark ? "rgba(148,163,214,0.28)" : "rgba(15,21,54,0.09)",
    pill: dark ? "rgba(123,123,255,0.18)" : "rgba(91,91,246,0.09)",
  };
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function drawResume(canvas, c) {
  const ctx = canvas.getContext("2d");
  const { width: W, height: H } = canvas;
  ctx.clearRect(0, 0, W, H);
  roundRect(ctx, 6, 6, W - 12, H - 12, 34);
  ctx.fillStyle = c.card;
  ctx.fill();
  ctx.lineWidth = 3;
  ctx.strokeStyle = c.cardEdge;
  ctx.stroke();

  // Avatar + name
  const grad = ctx.createLinearGradient(48, 48, 120, 120);
  grad.addColorStop(0, c.primary);
  grad.addColorStop(1, c.primary2);
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(84, 92, 38, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#fff";
  ctx.font = "700 30px 'Plus Jakarta Sans', Inter, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("P", 84, 94);
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = c.ink;
  ctx.font = "700 34px 'Plus Jakarta Sans', Inter, sans-serif";
  ctx.fillText("Your Name", 142, 86);
  ctx.fillStyle = c.muted;
  ctx.font = "500 22px Inter, sans-serif";
  ctx.fillText("Data Analyst · Dhaka", 142, 118);

  const section = (label, y) => {
    ctx.fillStyle = c.ink;
    ctx.font = "700 24px 'Plus Jakarta Sans', Inter, sans-serif";
    ctx.fillText(label, 48, y);
  };
  const bars = (y, widths) => widths.forEach((w, i) => {
    roundRect(ctx, 48, y + i * 28, w, 12, 6);
    ctx.fillStyle = c.line;
    ctx.fill();
  });

  section("Experience", 196);
  bars(218, [W - 150, W - 220, W - 180, W - 260]);
  section("Skills", 372);
  let x = 48;
  ctx.font = "600 20px Inter, sans-serif";
  SKILLS.forEach((skill) => {
    const w = ctx.measureText(skill).width + 30;
    roundRect(ctx, x, 392, w, 38, 19);
    ctx.fillStyle = c.pill;
    ctx.fill();
    ctx.fillStyle = c.primary;
    ctx.fillText(skill, x + 15, 418);
    x += w + 10;
  });
  section("Education", 486);
  bars(508, [W - 170, W - 250]);
}

function drawScore(canvas, c, value) {
  const ctx = canvas.getContext("2d");
  const { width: W, height: H } = canvas;
  ctx.clearRect(0, 0, W, H);
  roundRect(ctx, 6, 6, W - 12, H - 12, 30);
  ctx.fillStyle = c.card;
  ctx.fill();
  ctx.lineWidth = 3;
  ctx.strokeStyle = c.cardEdge;
  ctx.stroke();

  ctx.fillStyle = c.muted;
  ctx.font = "600 22px Inter, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("ATS Score", W / 2, 50);

  const cx = W / 2;
  const cy = 150;
  const r = 70;
  ctx.lineWidth = 16;
  ctx.lineCap = "round";
  ctx.strokeStyle = c.line;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.stroke();
  const grad = ctx.createLinearGradient(cx - r, cy - r, cx + r, cy + r);
  grad.addColorStop(0, c.good);
  grad.addColorStop(1, c.primary);
  ctx.strokeStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + (Math.PI * 2 * value) / 100);
  ctx.stroke();

  ctx.fillStyle = c.ink;
  ctx.font = "800 54px 'Plus Jakarta Sans', Inter, sans-serif";
  ctx.textBaseline = "middle";
  ctx.fillText(String(Math.round(value)), cx, cy + 2);
  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = c.good;
  ctx.font = "600 20px Inter, sans-serif";
  ctx.fillText("ATS friendly", cx, H - 30);
}

function glowTexture(THREE, color) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, color);
  g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

export function buildHeroScene(THREE, mount, { score = 92, onCardClick, reducedMotion = false } = {}) {
  let colors = palette();
  // Loop state, declared first: theme/resize callbacks read it.
  let shownScore = reducedMotion ? score : 0;
  let raf = 0;
  let running = false;
  let onScreen = true;
  let disposed = false;
  const disposables = [];
  const track = (obj) => {
    disposables.push(obj);
    return obj;
  };

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  mount.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
  camera.position.set(0, 0.2, 10);

  scene.add(new THREE.AmbientLight(0xffffff, 1.6));
  const keyLight = new THREE.DirectionalLight(0xffffff, 1.4);
  keyLight.position.set(4, 6, 8);
  scene.add(keyLight);

  const rig = new THREE.Group();
  scene.add(rig);

  // --- Resume card ---
  const resumeCanvas = document.createElement("canvas");
  resumeCanvas.width = 560;
  resumeCanvas.height = 600;
  drawResume(resumeCanvas, colors);
  const resumeTex = track(new THREE.CanvasTexture(resumeCanvas));
  resumeTex.colorSpace = THREE.SRGBColorSpace;
  resumeTex.anisotropy = 4;
  const card = new THREE.Mesh(
    track(new THREE.PlaneGeometry(2.8, 3.0)),
    track(new THREE.MeshBasicMaterial({ map: resumeTex, transparent: true }))
  );
  card.position.set(-0.2, 0.15, 0.6);
  card.rotation.set(0.04, -0.22, 0.02);
  rig.add(card);

  const glow = new THREE.Sprite(track(new THREE.SpriteMaterial({
    map: track(glowTexture(THREE, colors.primary)), transparent: true, opacity: colors.dark ? 0.55 : 0.35, depthWrite: false,
  })));
  glow.scale.set(7, 7, 1);
  glow.position.set(-0.1, 0, -0.6);
  rig.add(glow);

  // --- Score badge ---
  const scoreCanvas = document.createElement("canvas");
  scoreCanvas.width = 260;
  scoreCanvas.height = 300;
  drawScore(scoreCanvas, colors, reducedMotion ? score : 0);
  const scoreTex = track(new THREE.CanvasTexture(scoreCanvas));
  scoreTex.colorSpace = THREE.SRGBColorSpace;
  const badge = new THREE.Mesh(
    track(new THREE.PlaneGeometry(1.2, 1.38)),
    track(new THREE.MeshBasicMaterial({ map: scoreTex, transparent: true }))
  );
  badge.position.set(1.35, -0.55, 1.25);
  badge.rotation.set(0.02, -0.3, 0);
  rig.add(badge);

  // --- Job network: points + nearby connections ---
  const network = new THREE.Group();
  const nodeCount = 64;
  const nodes = [];
  for (let i = 0; i < nodeCount; i++) {
    const theta = (i / nodeCount) * Math.PI * 2 * 3.7;
    const radius = 3.2 + ((i * 37) % 17) / 10;
    nodes.push(new THREE.Vector3(
      Math.cos(theta) * radius,
      ((i * 53) % 41) / 10 - 2,
      Math.sin(theta) * radius * 0.55 - 1.5,
    ));
  }
  const pointsGeo = track(new THREE.BufferGeometry().setFromPoints(nodes));
  const pointsMat = track(new THREE.PointsMaterial({
    color: colors.primary, size: 0.09, transparent: true, opacity: 0.85, depthWrite: false,
  }));
  network.add(new THREE.Points(pointsGeo, pointsMat));
  const segments = [];
  for (let i = 0; i < nodeCount; i++) {
    for (let j = i + 1; j < nodeCount; j++) {
      if (nodes[i].distanceTo(nodes[j]) < 1.6) segments.push(nodes[i], nodes[j]);
    }
  }
  const linesMat = track(new THREE.LineBasicMaterial({
    color: colors.primary2, transparent: true, opacity: colors.dark ? 0.28 : 0.18, depthWrite: false,
  }));
  network.add(new THREE.LineSegments(track(new THREE.BufferGeometry().setFromPoints(segments)), linesMat));
  rig.add(network);

  // --- Path ribbon with a travelling pulse ---
  const curve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-4.6, -2.8, -1.2),
    new THREE.Vector3(-2.4, -2.1, 0.4),
    new THREE.Vector3(-0.4, -2.3, 1.0),
    new THREE.Vector3(1.6, -1.7, 0.2),
    new THREE.Vector3(4.2, -1.1, -1.4),
  ]);
  const tubeMats = [0, 1, 2].map((k) => track(new THREE.MeshBasicMaterial({
    color: k === 1 ? colors.primary : colors.primary2, transparent: true, opacity: 0.28 - k * 0.06, depthWrite: false,
  })));
  tubeMats.forEach((mat, k) => {
    const offset = new THREE.Vector3(0, k * 0.16, k * -0.12);
    const shifted = new THREE.CatmullRomCurve3(curve.points.map((p) => p.clone().add(offset)));
    rig.add(new THREE.Mesh(track(new THREE.TubeGeometry(shifted, 80, 0.05 + k * 0.01, 8, false)), mat));
  });
  const pulse = new THREE.Sprite(track(new THREE.SpriteMaterial({
    map: track(glowTexture(THREE, colors.primary)), transparent: true, depthWrite: false,
  })));
  pulse.scale.set(0.9, 0.9, 1);
  rig.add(pulse);

  // --- Floating glass cubes ---
  const cubeMat = track(new THREE.MeshStandardMaterial({
    color: colors.primary2, transparent: true, opacity: 0.45, roughness: 0.15, metalness: 0.1,
  }));
  const cubeGeo = track(new THREE.BoxGeometry(1, 1, 1));
  const cubes = [
    [-2.9, 1.7, -0.4, 0.42], [2.6, 2.0, -1.0, 0.32], [-3.2, -1.2, 0.6, 0.28], [3.1, -0.4, 0.4, 0.36], [0.9, 2.5, -1.6, 0.24],
  ].map(([x, y, z, s], i) => {
    const cube = new THREE.Mesh(cubeGeo, cubeMat);
    cube.position.set(x, y, z);
    cube.scale.setScalar(s);
    cube.userData = { baseY: y, phase: i * 1.3 };
    rig.add(cube);
    return cube;
  });

  // --- Interaction ---
  const pointer = { x: 0, y: 0 };
  const ndc = new THREE.Vector2(10, 10);
  const raycaster = new THREE.Raycaster();
  let hoverCard = false;
  const onPointerMove = (event) => {
    pointer.x = event.clientX / window.innerWidth - 0.5;
    pointer.y = event.clientY / window.innerHeight - 0.5;
    const rect = renderer.domElement.getBoundingClientRect();
    ndc.set(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
  };
  const onClick = () => hoverCard && onCardClick?.();
  window.addEventListener("pointermove", onPointerMove, { passive: true });
  renderer.domElement.addEventListener("click", onClick);

  // --- Theme changes: recolour without rebuilding ---
  const recolor = () => {
    colors = palette();
    drawResume(resumeCanvas, colors);
    resumeTex.needsUpdate = true;
    drawScore(scoreCanvas, colors, shownScore);
    scoreTex.needsUpdate = true;
    pointsMat.color.set(colors.primary);
    linesMat.color.set(colors.primary2);
    linesMat.opacity = colors.dark ? 0.28 : 0.18;
    glow.material.opacity = colors.dark ? 0.55 : 0.35;
    tubeMats.forEach((m, k) => m.color.set(k === 1 ? colors.primary : colors.primary2));
    cubeMat.color.set(colors.primary2);
    if (!running) renderer.render(scene, camera);
  };
  const themeObserver = new MutationObserver(recolor);
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  // Web fonts may finish loading after the first draw.
  document.fonts?.ready.then(() => !disposed && recolor());

  // --- Size ---
  const resize = () => {
    const { clientWidth: w, clientHeight: h } = mount;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // Pull back on narrow screens so the whole composition stays in frame.
    camera.position.z = w / h < 1 ? 12.5 : 10;
    camera.updateProjectionMatrix();
    if (!running) renderer.render(scene, camera);
  };
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(mount);

  // --- Loop (only while on screen and the tab is visible) ---
  const clock = new THREE.Clock();

  const frame = () => {
    const t = clock.getElapsedTime();
    if (shownScore < score) {
      shownScore = Math.min(score, score * (1 - Math.pow(1 - Math.min(t / 1.8, 1), 3)));
      drawScore(scoreCanvas, colors, shownScore);
      scoreTex.needsUpdate = true;
    }
    rig.rotation.y += (pointer.x * 0.35 - rig.rotation.y) * 0.05;
    rig.rotation.x += (pointer.y * 0.18 - rig.rotation.x) * 0.05;
    card.position.y = 0.15 + Math.sin(t * 0.9) * 0.08;
    badge.position.y = -0.55 + Math.sin(t * 0.9 + 1.2) * 0.1;
    network.rotation.y = t * 0.05;
    cubes.forEach((cube) => {
      cube.position.y = cube.userData.baseY + Math.sin(t * 0.8 + cube.userData.phase) * 0.18;
      cube.rotation.x = t * 0.25 + cube.userData.phase;
      cube.rotation.y = t * 0.3;
    });
    pulse.position.copy(curve.getPointAt((t * 0.12) % 1));

    raycaster.setFromCamera(ndc, camera);
    hoverCard = raycaster.intersectObject(card).length > 0;
    const targetScale = hoverCard ? 1.05 : 1;
    card.scale.setScalar(card.scale.x + (targetScale - card.scale.x) * 0.12);
    renderer.domElement.style.cursor = hoverCard && onCardClick ? "pointer" : "";

    renderer.render(scene, camera);
    raf = requestAnimationFrame(frame);
  };

  const start = () => {
    if (running || disposed || reducedMotion || !onScreen || document.hidden) return;
    running = true;
    raf = requestAnimationFrame(frame);
  };
  const stop = () => {
    running = false;
    cancelAnimationFrame(raf);
  };
  const visibilityObserver = new IntersectionObserver(([entry]) => {
    onScreen = entry.isIntersecting;
    onScreen ? start() : stop();
  });
  visibilityObserver.observe(mount);
  const onVisibility = () => (document.hidden ? stop() : start());
  document.addEventListener("visibilitychange", onVisibility);

  resize();
  renderer.render(scene, camera);
  start();

  return () => {
    disposed = true;
    stop();
    themeObserver.disconnect();
    resizeObserver.disconnect();
    visibilityObserver.disconnect();
    document.removeEventListener("visibilitychange", onVisibility);
    window.removeEventListener("pointermove", onPointerMove);
    renderer.domElement.removeEventListener("click", onClick);
    disposables.forEach((d) => d.dispose?.());
    renderer.dispose();
    renderer.domElement.remove();
  };
}
