/**
 * Example Mod — frontend (client side).
 *
 * This is the client half of the walkthrough mod. It showcases the client-side
 * modding API in one file:
 *
 *   * wsRegistry  — register handlers on engine hooks, and on this mod's own
 *                   custom hook.
 *   * gameState   — get / set / initialize / exists, input (isKeyDown),
 *                   addToSendBuffer (out), readServerMessages (in).
 *   * uiRegistry  — createView (bound handle), bindEvent, register_style.
 *
 * IMPORTANT — engine hooks vs. namespaced names:
 *   Engine hooks are always fully qualified ("core:tick", "core:init", ...).
 *   Everything THIS mod owns (handler names, state keys, UI names, message
 *   keys) is written UNQUALIFIED and the engine auto-prefixes it with the
 *   namespace from manifest.json ("example_mod"). So you write "my_counter"
 *   and it becomes "example_mod:my_counter" — you never write the prefix.
 *
 * This script is eval()'d during the WebSocket handshake (see the client
 * initialization flow). Because it is eval()'d, top-level `const`/`let` are
 * NOT visible to other scripts; attach shared objects to `window` if another
 * mod needs them. We keep everything local here, so no globals are needed.
 */

// --------------------------------------------------------------------------
// Inject this mod's styles. register_style returns an id we can clean up later.
// --------------------------------------------------------------------------
const styleId = uiRegistry.register_style(`
    .example-hud { position: fixed; bottom: 12px; left: 12px; max-width: 260px; }
    .example-hud .ui-row { margin-top: 6px; }
    .example-hud .ui-count { font-weight: bold; }
`);

// --------------------------------------------------------------------------
// Build a HUD panel. The builder returns an HTML string and runs lazily on
// mount(), inside this mod's namespace (createView captured it), so unqualified
// ui names and state keys are safe.
// --------------------------------------------------------------------------
function build_hud(ui, args, container) {
    return `
        <div class="example-hud ui-panel">
            <div class="ui-panel-title">Example Mod</div>
            <div class="ui-row"><span>World count</span><span data-count>0</span></div>
            <div class="ui-row"><span>My score</span><span data-score>0</span></div>
            <div class="ui-row"><span>Facing</span><span data-facing>0</span></div>
            <button class="ui-btn example-hit" data-hit>Add to score</button>
        </div>
    `;
}

// Register once + get a BOUND handle. This runs while "example_mod" is the
// active namespace, so "hud" resolves to "example_mod:hud" and the handle
// captures "example_mod" for all its later calls (at runtime the namespace
// stack is empty, but the handle re-enters it internally).
const hud = uiRegistry.createView("hud", build_hud);
hud.mount();

// --------------------------------------------------------------------------
// UI event handlers (registered on the mod's own event via uiRegistry.on).
// --------------------------------------------------------------------------
function score_pressed(payload, ui) {
    // The view is already mounted; bump the in-game score through gameState.
    const score = gameState.get(["score"], 0) + 1;
    gameState.set(["score"], score, true);
    hud.set("[data-score]", String(score));
    console.log(`[example_mod] score -> ${score}`);
}

// Register the handler on a namespaced UI event, then wire the DOM click to a
// bound dispatcher. bindEvent captures the namespace NOW and returns a closure
// that re-enters it when fired by the click.
uiRegistry.on("score_pressed", score_pressed);
hud.on("[data-hit]", "click", uiRegistry.bindEvent("score_pressed"));

// --------------------------------------------------------------------------
// core:init — one-time init payload from the server (e.g. server-computed
// per-player data delivered via add_to_client_sync during on_player_connect).
// --------------------------------------------------------------------------
function on_init(gameState) {
    for (const data of gameState.readServerMessages("example_data")) {
        console.log("[example_mod] init payload:", data);
        // Seed our client-side copy from the server's authoritative state.
        if (data && typeof data === "object" && "score" in data) {
            gameState.set(["score"], data.score, true);
        }
    }
}
wsRegistry.register_handler("core:init", on_init, "init-state");

// --------------------------------------------------------------------------
// core:tick — per-tick client logic. Read server messages, collect input,
// push it to the send buffer. Runs only after the client is initialized.
// --------------------------------------------------------------------------
function on_tick(gameState) {
    // Read this mod's messages from the server receive buffer. These were
    // pushed server-side via add_to_broadcast ("world_count") and
    // add_to_client_sync ("score"). readServerMessages auto-scopes to this
    // mod's namespace, so we pass the UNQUALIFIED key.
    const counts = gameState.readServerMessages("world_count");
    if (counts.length) {
        hud.set("[data-count]", String(counts[counts.length - 1]));
    }
    const scores = gameState.readServerMessages("score");
    if (scores.length) {
        gameState.set(["score"], scores[scores.length - 1], true);
        hud.set("[data-score]", String(scores[scores.length - 1]));
    }

    // Collect input and push it to the send buffer. The key is auto-namespaced
    // ("hello_key" -> "example_mod:hello_key"); the server reads it back under
    // that qualified name.
    const facing = gameState.get(["core:playerData", "yaw"], 0);
    hud.set("[data-facing]", String(facing));
    gameState.addToSendBuffer("hello_key", {
        facing,
        tick: Date.now(),
        keyW: gameState.isKeyDown("KeyW"),
    });
}
wsRegistry.register_handler("core:tick", on_tick, "tick-work");

// --------------------------------------------------------------------------
// core:update_camera — every render frame (requestAnimationFrame). Guarded:
// a bare engine may have no camera; if it does, we drive it from game state.
// --------------------------------------------------------------------------
function on_update_camera(gameState) {
    // Defensive: only touch window.camera if a scene/camera mod provided it.
    if (!window.camera) return;
    const yaw = gameState.get(["core:playerData", "yaw"], 0);
    const pitch = gameState.get(["core:playerData", "pitch"], 0);
    window.camera.rotation.order = "YXZ";
    window.camera.rotation.y = yaw;
    window.camera.rotation.x = pitch;
}
wsRegistry.register_handler("core:update_camera", on_update_camera, "update-camera");

// --------------------------------------------------------------------------
// A custom event hook owned by this mod (client side). The engine lets a mod
// create/dispatch its own hooks too. This is declared unqualified, so it
// resolves to "example_mod:my_event".
// --------------------------------------------------------------------------
function on_my_event(gameState) {
    console.log("[example_mod] custom client hook 'my_event' dispatched.");
}
wsRegistry.register_handler("my_event", on_my_event, "handle-my-event");

// --------------------------------------------------------------------------
// core:on_disconnect — client-side cleanup when the game socket closes.
// --------------------------------------------------------------------------
function on_disconnect(gameState) {
    hud.unmount();
    uiRegistry.clearStyles();
    console.log("[example_mod] cleaned up client UI on disconnect.");
}
wsRegistry.register_handler("core:on_disconnect", on_disconnect, "cleanup");

console.log("[example_mod] client loaded.");
