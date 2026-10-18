// -- Pre-initialization bootstrap ----------------------------------------------
// Sets up global error handlers, the client log WebSocket, the server
// connection overlay, the THREE.js scene, and finally bootstraps the game
// socket once the user submits server credentials.
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

// -- Connection Screen ---------------------
// The pre-connection screen (server URL, player name, password) is now owned by
// a mod's client_preload script (e.g. mods/connect_screen/client_preload.js),
// which runs before this file and installs itself on window.connectScreenProvider.
// The bootstrap simply awaits that provider. If no mod provides a connect screen,
// we resolve with an error (there is no server link to connect to).
function getServerURL() {
    if (typeof window.connectScreenProvider === "function") {
        return window.connectScreenProvider();
    }
    return Promise.reject(new Error(
        "No connect screen provider found. A mod that declares 'client_preload_js' must install itself on window.connectScreenProvider."
    ));
}

// -- Sequential dynamic script loader ------------------------------------------
// Loads scripts one at a time, waiting for each to finish before starting the
// next. Ensures the socket is initialized before all scripts that require it run.
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
// grid floor, and voxel geometry/materials. Those objects are attached to
// `window` so the mod's other client scripts can still reference them as bare
// globals, and so main.js's render loop can use them at runtime.

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
    socket.onclose = onSocketClose;
})().catch(err => {
    console.error("Bootstrap failed:", err);
    const div = document.getElementById("errorlog");
    if (div) div.innerText += `BOOTSTRAP ERROR: ${err}\n`;
});