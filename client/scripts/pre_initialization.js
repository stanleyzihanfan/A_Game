// -- Pre-initialization bootstrap ----------------------------------------------
// Sets up global error handlers, the client log WebSocket, the server
// connection overlay, the THREE.js scene, and finally bootstraps the
// game socket once the user submits server credentials.
window.onerror = function(msg, src, line, col, err) {
    const div = document.getElementById("errorlog");
    if (div) div.innerText += `ERROR: ${msg}\n  at ${src}:${line}:${col}\n`;
    return false;
};
window.onunhandledrejection = function(e) {
    const div = document.getElementById("errorlog");
    if (div) div.innerText += `UNHANDLED PROMISE: ${e.reason}\n`;
};

//Globals
/**
 * Helper function to encode messages using msgpack
 * @param {*} msg Message to encode
 * @returns Msgpack encoded message
 */
function encode(msg){
    return msgpack.encode(msg);
}

// -- Client log socket ----------------------------------------------------------
// Separate, independent WebSocket to the client asset server (this launcher),
// used only for console.log/warn/error + window.onerror/onunhandledrejection.
// Kept fully separate from the game `socket` — mods still report to the game
// server explicitly via their own ops.
let logSocket = null;
let logSocketReady = false;
const logQueue = [];
const LOG_QUEUE_MAX = 500;

function initLogSocket() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    logSocket = new WebSocket(`${proto}//${location.host}/clientlog`);
    logSocket.onopen = () => {
        logSocketReady = true;
        while (logQueue.length) {
            logSocket.send(logQueue.shift());
        }
    };
    logSocket.onclose = () => { logSocketReady = false; };
}

function sendClientLog(level, timestamp, args) {
    const payload = encode({
        level,
        timestamp,
        playerName,
        args: args.map(a => {
            try { return typeof a === "string" ? a : JSON.stringify(a); }
            catch { return String(a); }
        })
    });
    if (logSocketReady) {
        logSocket.send(payload);
    } else {
        logQueue.push(payload);
    }
}

initLogSocket();

//Derive web socket URL from API URL
function normalizeServerURL(input) {
    if (typeof input !== 'string') throw new TypeError("Input must be string!");
    let url = input.trim().replace(/\/+$/, "");        // strip trailing slash(es)
    if (!url) throw new Error("URL cannot be empty");
    url = url.replace(/^https/, "wss").replace(/^http/, "ws");
    console.log(url+"/server");
    return url + "/server";
}

// -- Connection Screen ---------------------
function getServerURL() {
    return new Promise((resolve) => {
        const overlay = document.getElementById("server-connect-overlay");
        const input = document.getElementById("server-url-input");
        const nameInput = document.getElementById("player-name-input");
        const passwordInput = document.getElementById("player-password-input");
        const button = document.getElementById("server-url-submit");
        const errorDiv = document.getElementById("server-url-error");

        input.value = localStorage.getItem("serverURL") || "";
        nameInput.value = localStorage.getItem("playerName") || "";

        function submit() {
            console.log("submit");
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

            overlay.style.display = "none";
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

// -- Sequential dynamic script loader ------------------------------------------
// Loads scripts one at a time, waiting for each to finish before starting the
// next. Ensures socket is initialized before all scrips that require it runs.
function loadScriptSequential(srcList) {
    return srcList.reduce((chain, src) => chain.then(() => new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = src;
        s.onload = resolve;
        s.onerror = () => reject(new Error(`Failed to load script: ${src}`));
        document.head.appendChild(s);
    })), Promise.resolve());
}

// -- Globals shared across scripts -----------------------------------------------
// These stay as top-level let/const so later classic <script> tags can see
// them as bare identifiers, same pattern as before.
let socket;                       // game socket, assigned once the URL is resolved
const wsRegistry = new Registry(); // WebSocket op handler registry
const gameState = new GameState(); // central client-side game state store
let playerName = "";
let playerPassword = "";

// -- THREE.js scene setup was moved into the scene_setup mod --------------------
// (mods/scene_setup/client.js). It owns the scene, renderer, camera, lighting,
// grid floor, resize handler, and voxel geometry/materials. Those objects are
// attached to `window` (scene, renderer, camera, voxelGeo, voxelMat, edgeMat)
// so the mod's player_position / testmod client scripts can still reference them
// as bare globals, and so main.js's render loop can use them at runtime.

// -- Bootstrap: resolve URL, open socket, then load the rest in order ----------
(async () => {
    // Load scripts and wait for user input concurrently
    const [, connectInfo] = await Promise.all([
        loadScriptSequential([
            "client/scripts/initialization.js",
            "client/scripts/main.js"
        ]),
        getServerURL()
    ]);

    playerName = connectInfo.playerName;
    playerPassword = connectInfo.password;
    socket = new WebSocket(connectInfo.url);
    socket.binaryType = "arraybuffer";
    socket.onopen = onSocketOpen;
    socket.onmessage = onSocketMessage;
})().catch(err => {
    console.error("Bootstrap failed:", err);
    const div = document.getElementById("errorlog");
    if (div) div.innerText += `BOOTSTRAP ERROR: ${err}\n`;
});