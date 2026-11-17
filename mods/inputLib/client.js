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
let touchStyleId = null;
// Set once mountTouch() succeeds, so the resize handler knows whether it has
// (or had) an overlay to restore. Pointers are tracked ourselves rather than
// relying on the CSS :active pseudo-class, which mobile browsers do not keep
// applied while a finger rests on an element. (Buttons are not wired to game
// state yet — this only drives the pressed look.)
const touchPointers = new Map();
let touchMounted = false;

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
    // -- Touch Handlers --------------------------------------------------------------
    // Wrapped in an async IIFE: the engine eval()s mod scripts as CLASSIC
    // scripts, where a top-level `await` is a SyntaxError that would abort this
    // whole file (taking the keyboard/mouse handlers with it). The IIFE keeps
    // the await inside an async function.
    //
    // The namespace is active only during this eval, so everything that needs
    // the mod's namespace (createView / register_style) is done BEFORE the
    // first await. Mounting happens after it, via the bound handle (which
    // re-enters the namespace itself), so runtime mounts work too.

    // Touch HTML lives in touch.html; the builder caches the fetched markup so
    // a remount (see the resize handler) never refetches or reparses it.
    let touchHTML = null;

    // Idempotent teardown. Safe to call more than once: a disconnect can fire
    // without a prior mount, and the resize handler remounts independently.
    // NOTE: touchView is intentionally NOT cleared here — mountTouch() needs the
    // bound handle to remount, and the handle is safe to reuse after unmount().
    function teardownTouch() {
        touchPointers.clear();
        if (touchView) touchView.unmount(); // removes the DOM nodes we appended
        touchMounted = false;
        if (touchLink) touchLink.remove();
        touchLink = null;
        if (touchStyleId) document.getElementById(touchStyleId)?.remove();
        touchStyleId = null;
    }

    // Mount the overlay into #ui-root. Idempotent: a no-op while already
    // mounted, so repeated resize/orientation events never stack copies.
    function mountTouch() {
        if (touchMounted) return;
        if (!touchHTML) {
            console.warn("[inputLib] touch UI not mounted yet: markup not loaded.");
            return;
        }
        if (!touchView) {
            console.error("[inputLib] touch UI handle missing; cannot mount.");
            return;
        }
        const el = touchView.mount();
        if (!el) {
            console.error("[inputLib] touch UI could not mount (no #ui-root).");
            return;
        }
        touchMounted = true;
        console.log("[inputLib] touch UI mounted.");
    }

    (async () => {
        //Load CSS using link tag
        touchLink = document.createElement("link");
        touchLink.rel = "stylesheet";
        touchLink.href = "/inputLib/touch.css";
        document.head.appendChild(touchLink);

        // Pressed-state rules. Generated so the selector outranks the base
        // `.touch-btn { background: ... }` rule in touch.css (#ui-root prefix)
        // and so the pressed look survives the browser dropping :active while
        // a finger is still down, as mobile browsers do.
        touchStyleId = uiRegistry.register_style(
            `
#ui-root .touch-btn.is-pressed,
#ui-root .touch-btn:active {
    background: rgba(42, 170, 102, 0.7);
    border-color: rgba(150, 255, 190, 0.9);
    transform: scale(0.94);
}
/* The look zone sits above the buttons in DOM order; keep the buttons tappable. */
.touch-look { z-index: 0; }
.touch-buttons, .touch-joy { z-index: 1; }
`,
            "ui-style-inputLib-touch-press",
        );

        //Register html while namespace is active & mount once html is received
        touchView = uiRegistry.createView("touch_ui", () => touchHTML);
        try {
            touchHTML = await loadText("/inputLib/touch.html");
            mountTouch();
        } catch (err) {
            console.error("[inputLib] touch UI failed to load:", err);
        }
    })();

    // Touch buttons. NOTE: these are INTENTIONALLY not wired to game state —
    // mapping data-key / data-action to ["core:keys", code] is not implemented
    // yet. What is wired here is the PRESSED LOOK (.is-pressed), so a tap gives
    // visible feedback on a real phone. Nothing is read from gameState.
    //
    // Listening on document (one listener per event, not per button) means a
    // finger that slides off a control still gets released.
    document.addEventListener("pointerdown", (e) => {
        if (otherInputOwner()) return;
        const btn = e.target.closest?.(".touch-btn");
        if (!btn) return;
        touchPointers.set(e.pointerId, btn);
        btn.classList.add("is-pressed");
        // Keep receiving this finger's events even if it leaves the button.
        try {
            btn.setPointerCapture(e.pointerId);
        } catch (_) {
            /* capture is best-effort */
        }
        e.preventDefault();
    });

    function releaseTouchPointer(e) {
        const btn = touchPointers.get(e.pointerId);
        if (!btn) return;
        touchPointers.delete(e.pointerId);
        btn.classList.remove("is-pressed");
    }
    // pointerup fires on the element even without capture; pointercancel covers
    // the OS stealing the touch (gesture, incoming call, app switch), and
    // lostpointercapture is the backstop.
    document.addEventListener("pointerup", releaseTouchPointer);
    document.addEventListener("pointercancel", releaseTouchPointer);
    document.addEventListener("lostpointercapture", releaseTouchPointer);

    // -- Remount after layout changes ------------------------------------------------
    // Rotation (and any viewport resize) can tear the overlay down: a transient
    // socket close fires core:on_disconnect, and uiRegistry has no client-side
    // lifecycle hook to bring it back. Remount here so the controls return the
    // next time a resize/resolution settles, instead of needing a page reload.
    let resizeTimer = null;
    function onViewportChange() {
        if (resizeTimer) clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            resizeTimer = null;
            mountTouch();
        }, 150);
    }
    window.addEventListener("resize", onViewportChange);
    window.addEventListener("orientationchange", onViewportChange);

    // Touch-only cleanup: on desktop this mod has no overlay, so it must not
    // touch touchView/touchLink there.
    wsRegistry.register_handler(
        "core:on_disconnect",
        () => teardownTouch(),
        "touch_cleanup",
    );
}

console.log(
    "[inputLib] full input handlers registered (keyboard + mouse + wheel).",
);
