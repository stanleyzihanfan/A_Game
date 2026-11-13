// -- Input delegation seam ------------------------------------------------------
// Mirrors the engine's window.inputMod contract (see engine/client/scripts/
// main.js). The engine's fallback handlers defer to window.inputMod when it owns
// input. BUT this mod IS that owner, so its own handlers must NOT suppress
// themselves. We distinguish our own claim (id === SELF_ID) from a DIFFERENT
// owner (e.g. another touch input mod that reclaims window.inputMod), and only
// defer to a foreign owner.
const SELF_ID = "inputLib";
// Touch detection. Also lets you force the touch UI on a desktop browser
// by opening the page with ?touch=1 (e.g. http://localhost:8000/?touch=1).
const IS_TOUCH =
    window.matchMedia("(pointer: coarse)").matches ||
    navigator.maxTouchPoints > 0 ||
    location.search.includes("touch=1");

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

// Touch-only resources. Declared at module scope (not inside the touch branch)
// because the core:on_disconnect handlers below run long after this script has
// finished evaluating and must still be able to see/tear them down.
let touchView = null;
let touchLink = null;

// ----------------------Helpers----------------------

/**
 * Fetch text file from server
 * @param {string} path - file path
 * @returns contents of text file
 */
async function loadText(path) {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error(`Could not load ${path} (HTTP ${res.status})`);
    return res.text();
}

/**
 * Sets the status of a key
 * @param {string} code - String name of key
 * @param {boolean} down - If it is pressed
 */
function setKey(code, down) {
    gameState.set(["core:keys", code], down, true);
}

/**
 * Sets the look direction of the player in game state
 * @param {number} dx - delta horizontal distance
 * @param {number} dy - delta vertical distance
 * @param {number} sensitivity - sensitivity factor
 */
function applyLook(dx, dy, sensitivity) {
    let yaw = gameState.get(["core:playerData", "yaw"]);
    let pitch = gameState.get(["core:playerData", "pitch"]);
    yaw -= dx * sensitivity;
    pitch -= dy * sensitivity;
    pitch = Math.max(-Math.PI / 2 + 0.01, Math.min(Math.PI / 2 - 0.01, pitch));
    gameState.set(["core:playerData", "yaw"], yaw);
    gameState.set(["core:playerData", "pitch"], pitch);
}

/**
 * Set the speed
 * @param {number} delta - delta distance
 * @param {number} sensitivity - sensitivity factor
 */
function changeSpeed(delta, sensitivity) {
    let speed = gameState.get(["core:playerData", "speed"]);
    speed -= delta * sensitivity;
    speed = Math.max(speed, 0);
    gameState.set(["core:playerData", "speed"], speed);
    document.getElementById("debug").textContent = "Speed: " + speed;
}

if (!IS_TOUCH) {
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
        if (!window.isGameFocused || !window.isGameFocused()) return;
        setKey(e.code, true);
        e.preventDefault();
        wsRegistry.dispatch("core:keydown", gameState);
    });

    document.addEventListener("keyup", (e) => {
        if (otherInputOwner()) return;
        if (!window.isGameFocused || !window.isGameFocused()) return;
        setKey(e.code, false);
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
        applyLook(e.movementX, e.movementY, SENSITIVITY);
    });

    // -- Mouse wheel (movement speed) ------------------------------------------------
    document.addEventListener("wheel", (e) => {
        if (otherInputOwner()) return;
        changeSpeed(e.deltaY, SCROLL_DIALATION);
    });
} else {
    // Touch Handlers
    // Wrapped in an async IIFE: the engine eval()s mod scripts as CLASSIC
    // scripts, where a top-level `await` is a SyntaxError that would abort this
    // whole file (taking the keyboard/mouse handlers with it). The IIFE keeps
    // the await inside an async function.
    //
    // The namespace is active only during this eval, so everything that needs
    // the mod's namespace (createView) stays captured here; the disconnect
    // handlers below are registered outside and use the bound handles.
    (async () => {
        let touchHTML = "";
        //Load CSS using link tag
        touchLink = document.createElement("link");
        touchLink.rel = "stylesheet";
        touchLink.href = "/inputLib/touch.css";
        document.head.appendChild(touchLink);

        //Register html while namespace is active & mount once html is received
        touchView = uiRegistry.createView("touch_ui", () => touchHTML);
        try {
            touchHTML = await loadText("/inputLib/touch.html");
            touchView.mount();
            console.log("[inputLib] touch UI mounted.");
        } catch (err) {
            console.error("[inputLib] touch UI failed to load:", err);
        }
    })();
}

wsRegistry.register_handler(
    "core:on_disconnect",
    () => {
        if (touchView) touchView.unmount();
        if (touchLink) touchLink.remove();
    },
    "touch_cleanup",
);

console.log(
    "[inputLib] full input handlers registered (keyboard + mouse + wheel).",
);
