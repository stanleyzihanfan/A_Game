// -- WebSocket bootstrap -------------------------------------------------------
// Raw message handler before the client is initialized.
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
    // Error handling
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
    console.log(`Client loading complete`);
    gameState.set(["core:initialized"],false,true);
    // -- Post-load hook ----------------------------------------------------------
    // Fires once, immediately after every mod's client script has been eval()ed
    // and registered, so mods can initialize their client-side state before the
    // socket handoff and the render loop start. Handlers are invoked inside their
    // own namespace. A failing handler is logged but doesn't break the handoff.
    try {
        wsRegistry.dispatch("core:on_mods_loaded", gameState);
    } catch (e) {
        console.error("  A mod's 'core:on_mods_loaded' handler failed; continuing client load");
    }
    // Hand off WebSocket message handling to gamestate
    socket.onmessage = (e) => {
        const msg = msgpack.decode(new Uint8Array(e.data));
        if (msg["op"]==="core:sync_with_client"){
            if (gameState.exists(["core:server_receive_buffer"])){
                let tmp=gameState.get(["core:server_receive_buffer"]);
                tmp.push(msg["data"]);
                gameState.set(["core:server_receive_buffer"],tmp);
            }else{
                gameState.set(["core:server_receive_buffer"],[],true);
                let tmp=gameState.get(["core:server_receive_buffer"]);
                tmp.push(msg["data"]);
                gameState.set(["core:server_receive_buffer"],tmp);
            }
            if (!gameState.get(["core:initialized"])){
                wsRegistry.dispatch("core:init", gameState);
                gameState.set(["core:initialized"],true);
            }
        }
    }
    socket.send(encode({"op": "client_init_done", "params": []}));
    loop();
}

function onSocketOpen() {
    WSConnectStartTime = performance.now();
    socket.send(encode({"op":"init","playerName":playerName,"psw":playerPassword}));
}

// Client-side disconnect handler. Mirrors the server's core:on_player_disconnect
// hook, but on the client. Fired whenever the game socket closes (server kick,
// network drop, tab close). Mods can register a "core:on_disconnect" handler to
// tear down UI, stop timers, or clean up state. Note that if the socket never
// fully opened (e.g. rejected before mods were streamed), wsRegistry may not
// have any handlers registered yet — dispatch() is a no-op then.
function onSocketClose(e) {
    console.log(`[core] Socket closed (code ${e && e.code !== undefined ? e.code : "unknown"}, reason: ${e && e.reason ? e.reason : ""})`);
    gameState.set(["core:initialized"], false, true);
    gameState.set(["core:disconnect"], {
        code: e && e.code !== undefined ? e.code : null,
        reason: e && e.reason ? e.reason : "",
        wasClean: e ? !!e.wasClean : false,
    });
    // Notify mods that the client is disconnecting. wsRegistry.dispatch re-enters
    // each handler's namespace, and also re-enters uiRegistry so unqualified ui
    // names resolve inside them.
    wsRegistry.dispatch("core:on_disconnect", gameState);
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
        // params: [modID, source, namespace] — namespace comes from the mod's
        // manifest.json and auto-prefixes unqualified names/keys the script
        // uses, mirroring the server-side mod loader.
        const [modID, src, namespace] = msg["params"];
        try {
            console.log(`Loading frontend mod script: ${modID}`);
            wsRegistry.pushNamespace(namespace);
            gameState.pushNamespace(namespace);
            uiRegistry.pushNamespace(namespace);
            try {
                eval(src);
            } finally {
                wsRegistry.popNamespace();
                gameState.popNamespace();
                uiRegistry.popNamespace();
            }
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