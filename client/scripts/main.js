// -- First-person camera controls ---------------------------------------------
//Configs
const keys = {};
let yaw = 0, pitch = 0;
let Speed = 8; // units per second
const SCROLL_DIALATION=0.005;
const SENSITIVITY = 0.002; // radians per pixel
const whitelist=[document.body,renderer.domElement];

// Elements considered "the game screen" — keydown/keyup are only
// processed for gameplay when one of these is focused. Everything else
// (text inputs, future UI panels, etc.) passes keys through untouched.
function isGameFocused() {
    const active = document.activeElement;
    return whitelist.includes(active);
}

document.addEventListener("keydown", e => { 
    if (!isGameFocused()) {
        return; // some other UI element is focused — let it handle typing normally
    }
    keys[e.code] = true;    
    e.preventDefault(); 
    wsRegistry.dispatch("main:keydown",gameState);
});
document.addEventListener("keyup", e => { 
    if (!isGameFocused()) {
        return;
    }
    keys[e.code] = false; 
    wsRegistry.dispatch("main:keyup",gameState);
});

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

// -- Resize handler ------------------------------------------------------------
window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

// -- Render loop ---------------------------------------------------------------
let last = performance.now();
let tickDelta=0
let tickrate=1/20;
function loop() {
    requestAnimationFrame(loop);
    
    const now = performance.now();
    const dt = Math.min((now - last) / 1000, 0.05); // cap at 50ms to avoid spiral
    last = now;
    tickDelta+=dt;
    while (tickDelta>=tickrate){
        wsRegistry.dispatch("main:tick",gameState);
        socket.send(encode({"op":"sync_with_server","params":gameState.get(["client_send_buffer"])}));
        //updateCamera(tickrate);
        tickDelta-=tickrate;
    }
    updateCamera(dt);
    renderer.render(scene, camera);
}