// -- First-person camera controls ---------------------------------------------
//Configs
// let yaw = 0, pitch = 0;
// let Speed = 8; // units per second
gameState.set(["playerData","yaw"],0,true);
gameState.set(["playerData","pitch"],0,true);
gameState.set(["playerData","speed"],8,true);
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
    gameState.set(["keys",e.code],true,true);
    e.preventDefault(); 
    wsRegistry.dispatch("core:keydown",gameState);
});
document.addEventListener("keyup", e => { 
    if (!isGameFocused()) {
        return;
    }
    gameState.set(["keys",e.code],false);
    wsRegistry.dispatch("core:keyup",gameState);
});

// Pointer lock
renderer.domElement.addEventListener("click", () => {
    renderer.domElement.requestPointerLock();
});
//Set camera look direction
document.addEventListener("mousemove", e => {
    if (document.pointerLockElement !== renderer.domElement) return;
    gameState.get(["playerData","yaw"],false) -= e.movementX * SENSITIVITY;
    gameState.get(["playerData","pitch"],false) -= e.movementY * SENSITIVITY;
    gameState.get(["playerData","pitch"],false) = Math.max(-Math.PI/2 + 0.01, Math.min(Math.PI/2 - 0.01, gameState.get(["playerData","pitch"])));
    // pitch -= e.movementY * SENSITIVITY;
    // pitch    = Math.max(-Math.PI/2 + 0.01, Math.min(Math.PI/2 - 0.01, pitch));
});

//Scroll wheel to control speed
document.addEventListener("wheel", e => {
    const Speed=gameState.get(["playerData","speed"],false);
    gameState-=e.deltaY*SCROLL_DIALATION,0;
    gameState.set(["playerData","speed"],Math.max(Speed,0));
    // Speed-=e.deltaY*SCROLL_DIALATION,0;
    // Speed=Math.max(Speed,0);
    document.getElementById("debug").textContent="Speed: "+Speed
})

// // Build a direction vector from yaw/pitch (Minecraft spectator style)
// const forward = new THREE.Vector3();
// const right = new THREE.Vector3();
// const up = new THREE.Vector3(0, 1, 0);


function updateCamera(dt) {
    // Rotation: yaw around world Y, pitch around local X
    camera.rotation.order = "YXZ";
    // camera.rotation.y = gameState.get(["playerData","yaw"]); 
    // camera.rotation.x = gameState.get(["playerData","pitch"]);

    // Movement directions derived from yaw only (no tilt on strafe/forward)
    // forward.set(Math.sin(yaw), 0, Math.cos(yaw)).negate();
    // right.crossVectors(forward, up).normalize();

    // const dist = Speed * dt;
    // const dist = gameState.get(["playerData","speed"])*dt;
    // if (keys["KeyW"]) camera.position.addScaledVector(forward, dist);
    // if (keys["KeyS"]) camera.position.addScaledVector(forward, -dist);
    // if (keys["KeyA"]) camera.position.addScaledVector(right, -dist);
    // if (keys["KeyD"]) camera.position.addScaledVector(right, dist);
    // if (keys["Space"]) camera.position.y += dist;
    // if (keys["ShiftLeft"] || keys["ShiftRight"]) camera.position.y -= dist;
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
    //TODO:Edit to use server
    while (tickDelta>=tickrate){
        gameState.set(["deltaTime"],tickrate,true);
        wsRegistry.dispatch("core:tick",gameState);
        socket.send(encode({"op":"sync_with_server","params":gameState.get(["client_send_buffer"])}));
        //updateCamera(tickrate);
        tickDelta-=tickrate;
    }
    wsRegistry.dispatch("core:update_camera",gameState);
    updateCamera(dt);
    renderer.render(scene, camera);
}