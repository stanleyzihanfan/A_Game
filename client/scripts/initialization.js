// -- WebSocket bootstrap -------------------------------------------------------
// Raw message handler before client is initialized
// Routes init, load_mod_js, and mods_ready — then hands off to mod dispatch
let WSConnectStartTime = -1;


function initClient() {
    // -- Console overrides (timestamp + forward to server) --------------------
    function formatCustom(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');
        return `[${year}-${month}-${day} ${hours}:${minutes}:${seconds}]`;
    }
    const originalLog = console.log;
    console.log = function(...args) {
        const timestamp = formatCustom(new Date());
        originalLog.apply(console, [timestamp, ...args]);
        sendClientLog("log", timestamp, args);
    }
    const originalWarn = console.warn;
    console.warn = function(...args) {
        const timestamp = formatCustom(new Date());
        originalWarn.apply(console, [timestamp, ...args]);
        sendClientLog("warn", timestamp, args);
    }
    const originalError = console.error;
    console.error = function(...args) {
        const timestamp = formatCustom(new Date());
        originalError.apply(console, [timestamp, ...args]);
        sendClientLog("error", timestamp, args);
    }
    //Error handling
    window.onerror = function(msg, src, line, col, err) {
        const div = document.getElementById("errorlog");
        if (div) div.innerText += `ERROR: ${msg}\n  at ${src}:${line}:${col}\n`;
        const timestamp = formatCustom(new Date());
        sendClientLog("error", timestamp, [`ERROR: ${msg}\n  at ${src}:${line}:${col}\n`]);
        return false;
    };
    window.onunhandledrejection = function(e) {
        const div = document.getElementById("errorlog");
        if (div) div.innerText += `UNHANDLED PROMISE: ${e.reason}\n`;
        const timestamp = formatCustom(new Date());
        sendClientLog("error", timestamp, [`UNHANDLED PROMISE: ${e.reason}\n`]);
    };
}

function onModsReady() {
    wsRegistry.register_handler("core:mods_ready");
    wsRegistry.dispatch("core:mods_ready", gameState);
    // -- Hand off WebSocket to gamestate ------------------------------
    socket.onmessage = (e) => {
        const msg = msgpack.decode(new Uint8Array(e.data));
        //Route message to game state
        if (msg["op"]==="core:sync_with_client"){
            if (gameState.exists(["server_receive_buffer"])){
                let tmp=gameState.get(["server_receive_buffer"]);
                tmp.push(msg["params"]);
                gameState.set(["server_receive_buffer"],tmp);
            }else{
                gameState.set(["server_receive_buffer"],[],true);
            }
        }
        else{
            serverData=gameState.get(["server_receive_buffer",msg["op"]],false);
            if (!gameState.exists(["server_receive_buffer",msg["op"]])){
                gameState.set(["server_receive_buffer",msg["op"]],[]);
                serverData=gameState.get(["server_receive_buffer",msg["op"]],false);
            }
            serverData.push(msg["params"]);
        }
    }
    console.log(`Client loading complete`);
    loop();
}

function onSocketOpen() {
    WSConnectStartTime = performance.now();
    socket.send(encode({"op":"init","playerName":playerName,"psw":playerPassword}));
}

// Init handler — only runs until mods_ready is received
function onSocketMessage(e) {
    const msg = msgpack.decode(new Uint8Array(e.data));
    if (msg["op"] === "init") {
        console.log("Initializing client...");
        initClient();
        return;
    }
    else if (msg["op"] === "load_mod_js") {
        const [modID, src] = msg["params"];
        try {
            console.log(`Loading frontend mod script: ${modID}`);
            eval(src);
            console.log(`  ${modID} loaded OK`);
        } catch(err) {
            const div = document.getElementById("errorlog");
            if (div) div.innerText += `MOD LOAD ERROR (${modID}): ${err}\n`;
        }
        return;
    }
    else if (msg["op"] === "mods_ready") {
        onModsReady();
        return;
    }else{
        console.warn("Backend attempted to access frontend handler " + msg["op"]+" before mod initialization finished with params "+msg["params"]+".");
    }
}