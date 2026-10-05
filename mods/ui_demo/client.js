/**
 * UI demo mod (frontend).
 *
 * Demonstrates the bound-handle workflow (uiRegistry.createView / bindEvent):
 * register ONCE at load time while the mod's namespace is active, then hold the
 * returned handle and mutate it during gameplay. Unlike raw names, the handle
 * carries its namespace with it, so runtime calls (clicks, timers) never need a
 * live namespace on the stack.
 *
 * It also shows the client-side disconnect hook (core:on_disconnect), which
 * tears down the HUD and clears the mod's styles when the game socket closes.
 */

// Inject this mod's styles. register_style returns an id we can clean up later.
const styleId = uiRegistry.register_style(`
    .ui-demo-hud { position: fixed; top: 12px; left: 12px; min-width: 220px; }
    .ui-demo-hud .ui-row { margin-top: 6px; }
    .ui-demo-hud .ui-btn { margin-right: 6px; }
`);

// -- Build a HUD panel ---------------------------------------------------------
// The builder returns an HTML string. It runs lazily on mount(), inside the
// view's namespace (createView captured it), so unqualified ui names are safe.
function build_hud(ui, args, container) {
    return `
        <div class="ui-demo-hud ui-panel">
            <div class="ui-panel-title">HUD</div>
            <div class="ui-row"><span>Health</span><span data-health>100</span></div>
            <div class="ui-row"><span>Mod</span><span data-mod>ui_demo</span></div>
            <button class="ui-btn ui-demo-hit" data-hit>Take Damage</button>
            <button class="ui-btn ui-btn--danger ui-demo-toggle" data-toggle>Toggle Panel</button>
        </div>
    `;
}

// -- Register once + get a bound handle ----------------------------------------
// This runs while "ui_demo" is the active namespace, so "hud" resolves to
// "ui_demo:hud" and the handle captures "ui_demo" for all its later calls.
const hud = uiRegistry.createView("hud", build_hud);
hud.mount();   // -> appends to #ui-root; safe to call here, safe to call later

// -- Wire the buttons via the handle -------------------------------------------
// Handlers read game state. They run inside the mod's namespace when bound.
function damage_handler(payload, ui) {
    const el = hud.el && hud.el.querySelector("[data-health]");
    if (el) {
        const next = Math.max(0, Number(el.textContent) - 5);
        el.textContent = next;
        console.log(`[ui_demo] health -> ${next}`);
    }
}
function toggle_handler(payload, ui) {
    if (hud.el) hud.el.style.display = hud.el.style.display === "none" ? "" : "none";
}

// Handlers are registered on the registry first (one per event name).
uiRegistry.on("health_damage", damage_handler);
uiRegistry.on("hud_toggle", toggle_handler);

// bindEvent captures the namespace NOW and returns a closure that re-enters it
// when fired. We wire the closure directly to the DOM, so a click ends up
// dispatching inside "ui_demo" — no runtime name resolution needed.
hud.on("[data-hit]", "click", uiRegistry.bindEvent("health_damage"));
hud.on("[data-toggle]", "click", uiRegistry.bindEvent("hud_toggle"));

// -- Live update from game state (core:tick) ------------------------------------
// update() runs inside the captured namespace, so unqualified get_el/set calls
// are safe. We refresh the speed readout each tick.
wsRegistry.register_handler("core:tick", function (gameState) {
    const speed = gameState.get(["core:playerData", "speed"], 8);
    hud.set("[data-mod]", `ui_demo (speed ${speed})`);
}, "tick_ui");

// -- Client-side disconnect cleanup ----------------------------------------------
// When the game socket closes, tear down the HUD and drop the injected styles.
wsRegistry.register_handler("core:on_disconnect", function () {
    hud.unmount();
    uiRegistry.clearStyles();
    console.log("[ui_demo] cleaned up on disconnect.");
}, "disconnect_cleanup");

console.log("[ui_demo] HUD mounted.");
