// -- Input delegation seam ------------------------------------------------------
// Mirrors the engine's window.inputMod contract (see engine/client/scripts/
// main.js). The engine's fallback handlers defer to window.inputMod when it owns
// input. BUT this mod IS that owner, so its own handlers must NOT suppress
// themselves. We distinguish our own claim (id === SELF_ID) from a DIFFERENT
// owner (e.g. a future touch input mod that reclaims window.inputMod), and only
// defer to a foreign owner.
const SELF_ID = "inputLib";

// The engine's fallback in main.js checks `window.inputMod` and defers whenever
// ANY mod owns input. We claim ownership here so the engine's fallback stands
// down (no double-handling). A later (e.g. touch) input mod can override
// window.inputMod to reclaim ownership.
window.inputMod = { ownsInput: () => true, id: SELF_ID };

// True only when a DIFFERENT mod owns gameplay input. Our own claim (id ===
// SELF_ID) is treated as "we are active" and does NOT suppress our handlers.
function otherInputOwner() {
    if (!window.inputMod) return false;
    if (window.inputMod.id === SELF_ID) return false; // our own claim — stay active
    if (typeof window.inputMod.ownsInput === "function")
        return !!window.inputMod.ownsInput();
    return !!window.inputMod.active;
}

const SCROLL_DIALATION = 0.005;
const SENSITIVITY = 0.002; // radians per pixel

// -- Keyboard handlers ----------------------------------------------------------
// Keydown/keyup are only processed for gameplay when the game screen is focused.
// isGameFocused() is renderer-specific, so it lives in the scene_setup mod and is
// exposed on `window` (streams in AFTER this mod). We resolve it lazily at
// runtime, so it is safe to reference here without it being defined yet.
document.addEventListener("keydown", (e) => {
    // If a different (touch) input mod owns gameplay input, let it handle it.
    if (otherInputOwner()) return;
    // Pass the event through when the scene mod hasn't loaded yet
    // (window.isGameFocused undefined, e.g. login screen) OR the focused
    // element is not the game screen (e.g. a text input).
    if (!window.isGameFocused || !window.isGameFocused()) {
        return;
    }
    gameState.set(["core:keys", e.code], true, true);
    e.preventDefault();
    wsRegistry.dispatch("core:keydown", gameState);
});

document.addEventListener("keyup", (e) => {
    if (otherInputOwner()) return;
    if (!window.isGameFocused || !window.isGameFocused()) {
        return;
    }
    gameState.set(["core:keys", e.code], false, true);
    wsRegistry.dispatch("core:keyup", gameState);
});

// -- Mouse look (pointer lock) ---------------------------------------------------
// The renderer's canvas is created by the scene_setup mod, which loads AFTER this
// mod. ensurePointerLock() is renderer-specific, so it lives in scene_setup and is
// exposed on `window`; the render loop calls it lazily via window.ensurePointerLock
// (which only runs after the scene mod streams in, so the canvas exists by then).
document.addEventListener("mousemove", (e) => {
    if (otherInputOwner()) return;
    if (
        !window.renderer ||
        document.pointerLockElement !== window.renderer.domElement
    )
        return;
    let yaw = gameState.get(["core:playerData", "yaw"]);
    let pitch = gameState.get(["core:playerData", "pitch"]);
    yaw -= e.movementX * SENSITIVITY;
    pitch -= e.movementY * SENSITIVITY;
    pitch = Math.max(-Math.PI / 2 + 0.01, Math.min(Math.PI / 2 - 0.01, pitch));
    gameState.set(["core:playerData", "yaw"], yaw);
    gameState.set(["core:playerData", "pitch"], pitch);
});

// -- Mouse wheel (movement speed) ------------------------------------------------
document.addEventListener("wheel", (e) => {
    if (otherInputOwner()) return;
    let speed = gameState.get(["core:playerData", "speed"]);
    speed -= e.deltaY * SCROLL_DIALATION;
    speed = Math.max(speed, 0);
    gameState.set(["core:playerData", "speed"], speed);
    document.getElementById("debug").textContent = "Speed: " + speed;
});

console.log(
    "[inputLib] full input handlers registered (keyboard + mouse + wheel).",
);
