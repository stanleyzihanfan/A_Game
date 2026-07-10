//Error debug script
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

//Derive web socket URL from API URL
function normalizeServerURL(input) {
    if (typeof input !== 'string') throw new TypeError("Input must be string!");
    let url = input.trim().replace(/\/+$/, "");        // strip trailing slash(es)
    if (!url) throw new Error("URL cannot be empty");
    url = url.replace(/^https/, "wss").replace(/^http/, "ws");
    return url + "/server";
}

// -- Server URL entry (DOM-based, replaces window.prompt) ---------------------
// window.prompt is blocked or silently no-ops in many embedded webviews
// (VSCode preview, Electron, etc.), so this uses the overlay markup in
// frontend.html instead. Works identically everywhere. Doubles as the seed
// for a future server-select screen.
function getServerURL() {
    return new Promise((resolve) => {
        const overlay = document.getElementById("server-connect-overlay");
        const input = document.getElementById("server-url-input");
        const button = document.getElementById("server-url-submit");
        const errorDiv = document.getElementById("server-url-error");

        input.value = localStorage.getItem("serverURL") || "";
        input.focus();

        function submit() {
            const raw = input.value.trim();
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
            overlay.style.display = "none";
            button.removeEventListener("click", submit);
            input.removeEventListener("keydown", onKeydown);
            resolve(normalized);
        }
        function onKeydown(e) {
            if (e.key === "Enter") submit();
        }

        button.addEventListener("click", submit);
        input.addEventListener("keydown", onKeydown);
    });
}

// -- Sequential dynamic script loader ------------------------------------------
// Loads scripts one at a time, waiting for each to finish before starting the
// next. Needed because initialization.js/post_initialization.js/main.js all
// assume `socket` already exists, and socket creation now depends on the
// async URL prompt above.
function loadScriptSequential(srcList) {
    return srcList.reduce((chain, src) => chain.then(() => new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = src;
        s.onload = resolve;
        s.onerror = () => reject(new Error(`Failed to load script: ${src}`));
        document.head.appendChild(s);
    })), Promise.resolve());
}

// -- Globals used by later scripts ----------------------------------------------
// These stay as top-level let/const so later classic <script> tags can see
// them as bare identifiers, same pattern as before.
let socket;                       // assigned once the URL is resolved, below
const wsRegistry = new Registry();
const gameState = new GameState();
let clientID = -1;

// -- THREE.js Scene setup --------------------------------------------------------------
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87ceeb);
scene.fog = new THREE.Fog(0x87ceeb, 20, 80);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
document.body.appendChild(renderer.domElement);
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 200);
camera.position.set(5, 4, 10); // start position

// -- Lighting -----------------------------------------------------------------
const sun = new THREE.DirectionalLight(0xffffff, 1.0);
sun.position.set(10, 20, 10);
sun.castShadow = true;
scene.add(sun);
scene.add(new THREE.AmbientLight(0xffffff, 0.4));

// -- Grid floor ---------------------------------------------------------------
scene.add(new THREE.GridHelper(40, 40, 0x444444, 0x222222));

// -- Voxel definition ----------------------------------------------------------
const voxelGeo = new THREE.BoxGeometry(1, 1, 1);
const voxelMat = new THREE.MeshLambertMaterial({ color: 0x4a90d9 });
const edgeMat  = new THREE.LineBasicMaterial({ color: 0x1a3a5c });

// -- Bootstrap: resolve URL, open socket, then load the rest in order ----------
(async () => {
    const socketUrl = await getServerURL();
    socket = new WebSocket(socketUrl);
    socket.binaryType = "arraybuffer";

    await loadScriptSequential([
        "client/scripts/initialization.js",
        "client/scripts/post_initialization.js",
        "client/scripts/main.js"
    ]);
})().catch(err => {
    console.error("Bootstrap failed:", err);
    const div = document.getElementById("errorlog");
    if (div) div.innerText += `BOOTSTRAP ERROR: ${err}\n`;
});