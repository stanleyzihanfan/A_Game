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
//Global Vars
//Web Socket variables
const socketUrl=location.href.replace(/^http/,"ws")+"server";
const socket= new WebSocket(socketUrl);
socket.binaryType="arraybuffer";
//WebSocket Dispatch Table
const wsDispatch={};
//Client ID
let clientID=-1;
// -- THREE.js Scene setup --------------------------------------------------------------
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87ceeb);
//scene.fog = new THREE.Fog(0x87ceeb, 20, 80);
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
