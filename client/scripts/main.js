// -- First-person camera controls ---------------------------------------------
//Configs
const keys = {};
let yaw = 0, pitch = 0;
let Speed = 8; // units per second
const SCROLL_DIALATION=0.005;
const SENSITIVITY = 0.002; // radians per pixel

document.addEventListener("keydown", e => { keys[e.code] = true;    e.preventDefault(); });
document.addEventListener("keyup",     e => { keys[e.code] = false; });

// Pointer lock
renderer.domElement.addEventListener("click", () => {
    renderer.domElement.requestPointerLock();
});
//Set camera look direction
document.addEventListener("mousemove", e => {
    if (document.pointerLockElement !== renderer.domElement) return;
    yaw     -= e.movementX * SENSITIVITY;
    pitch -= e.movementY * SENSITIVITY;
    pitch    = Math.max(-Math.PI/2 + 0.01, Math.min(Math.PI/2 - 0.01, pitch));
});

//Scroll wheel to control speed
document.addEventListener("wheel", e => {
    Speed-=e.deltaY*SCROLL_DIALATION,0;
    Speed=Math.max(Speed,0);
    document.getElementById("debug").textContent="Speed: "+Speed
})

// Build a direction vector from yaw/pitch (Minecraft spectator style)
const forward = new THREE.Vector3();
const right = new THREE.Vector3();
const up = new THREE.Vector3(0, 1, 0);

function updateCamera(dt) {
    // Rotation: yaw around world Y, pitch around local X
    camera.rotation.order = "YXZ";
    camera.rotation.y = yaw;
    camera.rotation.x = pitch;

    // Movement directions derived from yaw only (no tilt on strafe/forward)
    forward.set(Math.sin(yaw), 0, Math.cos(yaw)).negate();
    right.crossVectors(forward, up).normalize();

    const dist = Speed * dt;
    if (keys["KeyW"]) camera.position.addScaledVector(forward, dist);
    if (keys["KeyS"]) camera.position.addScaledVector(forward, -dist);
    if (keys["KeyA"]) camera.position.addScaledVector(right, -dist);
    if (keys["KeyD"]) camera.position.addScaledVector(right, dist);
    if (keys["Space"]) camera.position.y += dist;
    if (keys["ShiftLeft"] || keys["ShiftRight"]) camera.position.y -= dist;
}

// -- Render loop ---------------------------------------------------------------
let last = performance.now();
function loop() {
    requestAnimationFrame(loop);
    const now = performance.now();
    const dt = Math.min((now - last) / 1000, 0.05); // cap at 50ms to avoid spiral
    last = now;
    updateCamera(dt);
    renderer.render(scene, camera);
}
loop();

// -- Resize handler ------------------------------------------------------------
window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});