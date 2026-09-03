// -- First-person camera controls ---------------------------------------------
//Configs
gameState.set(["playerData","yaw"],0,true);
gameState.set(["playerData","pitch"],0,true);
gameState.set(["playerData","speed"],8,true); //units per second
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
    let yaw=gameState.get(["playerData","yaw"]);
    let pitch=gameState.get(["playerData","pitch"]);
    yaw -= e.movementX * SENSITIVITY;
    pitch -= e.movementY * SENSITIVITY;
    pitch = Math.max(-Math.PI/2 + 0.01, Math.min(Math.PI/2 - 0.01, pitch));
    gameState.set(["playerData","yaw"],yaw);
    gameState.set(["playerData","pitch"],pitch);
});

//Scroll wheel to control speed
document.addEventListener("wheel", e => {
    let speed=gameState.get(["playerData","speed"]);
    speed-=e.deltaY*SCROLL_DIALATION,0;
    speed=Math.max(speed,0);
    gameState.set(["playerData","speed"],speed);
    document.getElementById("debug").textContent="Speed: "+speed
})

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
gameState.set(["client_send_buffer"],[],true);
function loop() {
    requestAnimationFrame(loop);
    
    const now = performance.now();
    const dt = Math.min((now - last) / 1000, 0.05); // cap at 50ms to avoid spiral
    last = now;
    tickDelta+=dt;
    while (tickDelta>=tickrate){
        gameState.set(["deltaTime"],tickrate,true);
        wsRegistry.dispatch("core:tick",gameState);
        socket.send(encode({"op":"sync_with_server","params":gameState.get(["client_send_buffer"])}));
        gameState.set(["client_send_buffer"],{},true);
        tickDelta-=tickrate;
        gameState.set(["server_receive_buffer"],[])
    }
    wsRegistry.dispatch("core:update_camera",gameState);
    renderer.render(scene, camera);
}