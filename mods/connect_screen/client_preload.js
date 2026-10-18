/**
 * Connection Screen mod (preload).
 *
 * This script runs BEFORE the bootstrap scripts (pre_initialization.js,
 * main.js). It owns everything about the pre-connection screen:
 *
 *   - the overlay markup (server link, player name, password, connect button);
 *   - the presentation logic (show / hide / validation / error text);
 *   - the provider that returns the resolved connect info to the bootstrap.
 *
 * Why a PRELOAD script and not client_js:
 * The normal mod client_js scripts are streamed over the WebSocket AFTER the
 * user connects (and after the connect-guard decides). The connect screen has
 * to exist BEFORE any connection is made, so it cannot be a normal mod script.
 * The engine's client asset server (client/launcher.py) reads this mod's
 * "client_preload_js" from its manifest and injects it into the page early,
 * so it can host the screen and provide the connect info that the bootstrap
 * collects before opening the socket.
 *
 * The contract with the bootstrap (pre_initialization.js):
 *   - The bootstrap calls window.connectScreenProvider() and awaits it.
 *   - The provider resolves with { url, playerName, password } (url already
 *     normalized to its WebSocket form) or rejects with an Error.
 *
 * The mod provides a namespaced mount so it is discoverable, and it is
 * defensive: if another provider already claimed the connect screen, it backs
 * off rather than duplicating the UI.
 */

(() => {
    // -- Namespace -------------------------------------------------------------
    // This is a PRELOAD script, so it does not get auto-namespaced by the mod
    // loader (that only happens for client_js streamed through load_mod_js).
    // Declared here for clarity and to namespace the mount id.
    const NS = "connect_screen";
    const SCREEN_ID = "server-connect-overlay";

    // -- Back off if another provider owns the connect screen ------------------
    // Preload scripts all run before the bootstrap. If the engine (or another
    // preload mod) already installed a connect screen, we do not duplicate it.
    if (!!window.connectScreenProvider) {
        console.warn(`[${NS}] A connect-screen provider is already installed; not creating a second screen.`);
        return;
    }

    // -- Inject this mod's styles ---------------------------------------------
    // The preload script is NOT auto-namespaced, so it must register styles
    // itself. It appends a <style> element rather than relying on the engine's
    // styles.css (the engine no longer ships connect-screen CSS).
    function injectStyles() {
        const style = document.createElement("style");
        style.id = `${NS}-styles`;
        style.textContent = `
            #server-connect-overlay {
                position: fixed; inset: 0;
                background: rgba(0,0,0,0.85);
                display: none; align-items: center; justify-content: center;
                z-index: 1000;
            }
            #server-connect-overlay.connect-visible { display: flex; }
            .connect-box {
                background: #111; border: 1px solid #444; border-radius: 8px;
                padding: 24px; width: min(90vw, 420px);
                font: 14px monospace; color: #fff;
                display: flex; flex-direction: column; gap: 10px;
            }
            .connect-title { font: bold 18px monospace; color: #fff; text-align: center; margin-bottom: 4px; }
            .connect-box label { color: #ccc; }
            .connect-box input {
                padding: 8px; font: 14px monospace;
                background: #000; color: #0f0; border: 1px solid #444; border-radius: 4px;
            }
            .connect-btn {
                padding: 8px; font: 14px monospace; cursor: pointer;
                background: #2a6; color: #fff; border: none; border-radius: 4px;
            }
            .connect-btn:hover { background: #3b7; }
            .connect-error { color: #ff4444; min-height: 16px; }
        `;
        document.head.appendChild(style);
    }

    // -- Build the overlay -------------------------------------------------------
    function buildOverlay() {
        const overlay = document.createElement("div");
        overlay.id = SCREEN_ID;
        overlay.innerHTML = `
            <div class="connect-box">
                <h1 class="connect-title">Connect</h1>

                <label for="server-url-input">Server link</label>
                <input type="text" id="server-url-input" placeholder="https://xxxx.trycloudflare.com or http://localhost:5000">

                <label for="player-name-input">Player name</label>
                <input type="text" id="player-name-input" placeholder="Enter a name">

                <label for="player-password-input">Password</label>
                <input type="password" id="player-password-input" placeholder="Password">

                <button class="connect-btn" id="server-url-submit">Connect</button>
                <div class="connect-error" id="server-url-error"></div>
            </div>
        `;

        // Keep the IDs the bootstrap may reference, and attach to <body> AFTER
        // the other body content so it sits on top (z-index handles stacking).
        document.body.appendChild(overlay);
        return overlay;
    }

    // -- URL normalization (moved from pre_initialization.js) --------------------
    function normalizeServerURL(input) {
        if (typeof input !== "string") throw new TypeError("Input must be string!");
        let url = input.trim().replace(/\/+$/, "");      // strip trailing slash(es)
        if (!url) throw new Error("URL cannot be empty");
        url = url.replace(/^https/, "wss").replace(/^http/, "ws");
        return url + "/server";
    }

    // -- Provider ---------------------------------------------------------------
    // The bootstrap awaits this. It shows the screen, collects the inputs, and
    // resolves with { url, playerName, password }.
    function getServerURL() {
        return new Promise((resolve, reject) => {
            const overlay = document.getElementById(SCREEN_ID);
            if (!overlay) {
                reject(new Error("Connect screen overlay not found"));
                return;
            }
            const input = document.getElementById("server-url-input");
            const nameInput = document.getElementById("player-name-input");
            const passwordInput = document.getElementById("player-password-input");
            const button = document.getElementById("server-url-submit");
            const errorDiv = document.getElementById("server-url-error");

            input.value = localStorage.getItem("serverURL") || "";
            nameInput.value = localStorage.getItem("playerName") || "";

            function show() { overlay.classList.add("connect-visible"); }
            function hide() { overlay.classList.remove("connect-visible"); }
            show();

            function submit() {
                const raw = input.value.trim();
                const playerName = nameInput.value.trim();
                const password = passwordInput.value; // not trimmed — spaces may be intentional

                if (!raw) {
                    errorDiv.innerText = "Please enter a server link.";
                    return;
                }
                let normalized;
                try {
                    normalized = normalizeServerURL(raw);
                } catch (e) {
                    errorDiv.innerText = `Invalid URL: ${e.message}`;
                    return;
                }

                localStorage.setItem("serverURL", raw);
                localStorage.setItem("playerName", playerName);
                // password intentionally not persisted

                hide();
                button.removeEventListener("click", submit);
                input.removeEventListener("keydown", onKeydown);
                nameInput.removeEventListener("keydown", onKeydown);
                passwordInput.removeEventListener("keydown", onKeydown);

                resolve({ url: normalized, playerName, password });
            }
            function onKeydown(e) {
                if (e.key === "Enter") submit();
            }

            button.addEventListener("click", submit);
            input.addEventListener("keydown", onKeydown);
            nameInput.addEventListener("keydown", onKeydown);
            passwordInput.addEventListener("keydown", onKeydown);
        });
    }

    // -- Install ----------------------------------------------------------------
    injectStyles();
    buildOverlay();

    // Expose the provider to the bootstrap. Use a distinct, namespaced global so
    // other preload mods can coexist.
    window.connectScreenProvider = getServerURL;
    console.log(`[${NS}] connect screen installed (preload).`);
})();
