// -- First-person camera controls ---------------------------------------------
// Initializes the player's look/rotation state and the movement speed.
gameState.set(["core:playerData","yaw"],0,true);
gameState.set(["core:playerData","pitch"],0,true);
// Base movement speed in world units per second
gameState.set(["core:playerData","speed"],8,true);
const SCROLL_DIALATION=0.005;
const SENSITIVITY = 0.002; // radians per pixel

// Elements considered "the game screen" — keydown/keyup are only
// processed for gameplay when one of these is focused. Everything else
// (text inputs, future UI panels, etc.) passes keys through untouched.
// isGameFocused() is renderer-specific, so it now lives in the scene_setup mod
// and is exposed on `window` (it streams in AFTER this bootstrap script). We
// resolve it lazily at runtime via window.isGameFocused.

// -- Input handling: keyboard ---------------------------------------------------
document.addEventListener("keydown", e => { 
    // Pass the event through (don't capture/preventDefault) when the scene
    // mod hasn't loaded yet (window.isGameFocused undefined, e.g. login
    // screen) OR the focused element is not the game screen (e.g. a text
    // input). Only then do we treat it as gameplay input.
    if (!window.isGameFocused || !window.isGameFocused()) {
        return; // some other UI element is focused — let it handle typing normally
    }
    gameState.set(["core:keys",e.code],true,true);
    e.preventDefault(); 
    wsRegistry.dispatch("core:keydown",gameState);
});
document.addEventListener("keyup", e => { 
    if (!window.isGameFocused || !window.isGameFocused()) {
        return;
    }
    gameState.set(["core:keys",e.code],false,true);
    wsRegistry.dispatch("core:keyup",gameState);
});

// -- Input handling: mouse (pointer lock + look + scroll) ------------------------
// Pointer lock
// The renderer's canvas is created by the scene_setup mod, which loads over the
// WebSocket AFTER this bootstrap script. ensurePointerLock() is renderer-
// specific, so it now lives in the scene_setup mod and is exposed on `window`;
// the render loop calls it lazily via window.ensurePointerLock (which only
// runs after the scene mod streams in, so the canvas exists by then).
//Set camera look direction
document.addEventListener("mousemove", e => {
    if (!window.renderer || document.pointerLockElement !== window.renderer.domElement) return;
    let yaw=gameState.get(["core:playerData","yaw"]);
    let pitch=gameState.get(["core:playerData","pitch"]);
    yaw -= e.movementX * SENSITIVITY;
    pitch -= e.movementY * SENSITIVITY;
    pitch = Math.max(-Math.PI/2 + 0.01, Math.min(Math.PI/2 - 0.01, pitch));
    gameState.set(["core:playerData","yaw"],yaw);
    gameState.set(["core:playerData","pitch"],pitch);
});

// Scroll wheel to control movement speed
document.addEventListener("wheel", e => {
    let speed=gameState.get(["core:playerData","speed"]);
    speed -= e.deltaY * SCROLL_DIALATION;
    speed = Math.max(speed, 0);
    gameState.set(["core:playerData","speed"], speed);
    document.getElementById("debug").textContent = "Speed: " + speed;
});

// -- Resize handler ------------------------------------------------------------
// Owned by the scene_setup mod now (it owns the renderer and camera). No
// duplicate handler here.

// -- Render loop ---------------------------------------------------------------
let last = performance.now();
let tickDelta = 0;            // accumulator for fixed game ticks
let tickrate = 1 / 20;        // 20 ticks per second
gameState.set(["core:client_send_buffer"], {}, true);

function loop() {
    requestAnimationFrame(loop);

    const now = performance.now();
    // Cap delta time to prevent a spiral of death if the tab is backgrounded
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;

    tickDelta += dt;
    // Fixed timestep update — runs as many ticks as needed to catch up
    while (tickDelta >= tickrate) {
        gameState.set(["core:deltaTime"], tickrate, true);
        if (gameState.get(["core:initialized"]))
            wsRegistry.dispatch("core:tick", gameState);
        // Send collected client input to server
        socket.send(encode({"op": "sync_with_server", "params": gameState.get(["core:client_send_buffer"])}));
        gameState.set(["core:client_send_buffer"], {}, true);
        tickDelta -= tickrate;
        // Clear receive buffer after processing
        gameState.set(["core:server_receive_buffer"], []);
    }
    // Make sure the pointer-lock listener is attached once the scene mod's
    // canvas exists (the scene mod loads right before mods_ready).
    if (window.ensurePointerLock) window.ensurePointerLock();
    // Update camera and render frame
    wsRegistry.dispatch("core:update_camera", gameState);
    if (window.renderer && window.scene && window.camera) {
        window.renderer.render(window.scene, window.camera);
    }
}