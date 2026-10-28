/**
 * Scene setup mod (frontend).
 *
 * Owns all the Three.js scene setup that used to live inline in
 * client/scripts/pre_initialization.js: scene/renderer/camera, lighting, the
 * grid floor, and voxel geometry + materials. It also owns the window resize
 * handler so the renderer and camera stay in sync.
 *
 * Because mod client scripts are eval()'d (see initialization.js
 * onSocketMessage -> "load_mod_js"), top-level `const`/`let` here would NOT be
 * visible to the rest of the client. So every object is attached to `window`,
 * which is how the other mods read `camera`, `scene`, `voxelGeo`, etc.
 *
 * The scene is created at mod-load time, during the WebSocket handshake AFTER
 * the bootstrap scripts run. main.js references these objects only at runtime,
 * so by then they exist on window.
 *
 * Namespacing: this mod's manifest.json declares "namespace": "scene_setup".
 */

// -- Scene ---------------------------------------------------------------------
window.scene = new THREE.Scene();
window.scene.background = new THREE.Color(0x87ceeb);
window.scene.fog = new THREE.Fog(0x87ceeb, 20, 80);

// -- Renderer ------------------------------------------------------------------
window.renderer = new THREE.WebGLRenderer({ antialias: true });
// Scale for the device pixel ratio so text/canvas stay crisp on high-DPI (and
// mobile) displays instead of rendering at CSS resolution and upscaling.
window.renderer.setPixelRatio(window.devicePixelRatio || 1);
window.renderer.setSize(window.innerWidth, window.innerHeight);
window.renderer.shadowMap.enabled = true;
document.body.appendChild(window.renderer.domElement);

// -- Camera --------------------------------------------------------------------
window.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 200);
window.camera.position.set(5, 4, 10); // start position

// -- Lighting ------------------------------------------------------------------
const sun = new THREE.DirectionalLight(0xffffff, 1.0);
sun.position.set(10, 20, 10);
sun.castShadow = true;
window.scene.add(sun);
window.scene.add(new THREE.AmbientLight(0xffffff, 0.4));

// -- Grid floor ----------------------------------------------------------------
const grid=new THREE.GridHelper(40,40,0x444444, 0x222222);
grid.name="gridFloor";
window.scene.add(grid);

// -- Voxel definition ----------------------------------------------------------
window.voxelGeo = new THREE.BoxGeometry(1, 1, 1);
window.voxelMat = new THREE.MeshLambertMaterial({ color: 0x4a90d9 });
window.edgeMat  = new THREE.LineBasicMaterial({ color: 0x1a3a5c });
const voxelTest=new THREE.Mesh(voxelGeo,voxelMat);
voxelTest.position.set(2,2,0);
window.scene.add(voxelTest);

// -- Renderer-scoped helpers ---------------------------------------------------
// These used to live in client/scripts/main.js, but they are renderer-specific.
// They are exposed on `window` because main.js runs during bootstrap (before
// this mod streams in), so it calls them lazily via window.isGameFocused /
// window.ensurePointerLock.
window.isGameFocused = function() {
    const active = document.activeElement;
    if (active === document.body) return true;
    if (window.renderer && active === window.renderer.domElement) return true;
    return false;
};

// Coarse-pointer (touch) detection: mobile browsers don't implement the Pointer
// Lock API, so requestPointerLock() is a no-op/rejects. On touch devices, look
// is handled by the input mod's drag-look zone instead (which writes
// ["core:playerData","yaw"/"pitch"]), so we don't wire a tap-to-lock click here.
// window.isCoarsePointer is a plain capability test any mod can read/short-circuit.
window.isCoarsePointer = function () {
    return (window.matchMedia && window.matchMedia("(pointer: coarse)").matches)
        || (navigator.maxTouchPoints && navigator.maxTouchPoints > 0);
};

let pointerLockAttached = false;
window.ensurePointerLock = function() {
    if (pointerLockAttached) return;
    if (!window.renderer || !window.renderer.domElement) return;
    // On touch devices there is no pointer lock to acquire — the input mod owns
    // look. Still record the flag so main.js's condition stays consistent.
    pointerLockAttached = true;
    if (window.isCoarsePointer && window.isCoarsePointer()) {
        return;
    }
    window.renderer.domElement.addEventListener("click", () => {
        window.renderer.domElement.requestPointerLock();
    });
};

// -- Resize handler ------------------------------------------------------------
// Owned here because this mod owns the renderer and camera it resizes.
window.addEventListener("resize", () => {
    window.camera.aspect = window.innerWidth / window.innerHeight;
    window.camera.updateProjectionMatrix();
    window.renderer.setSize(window.innerWidth, window.innerHeight);
});
