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
        socket.send(msgpack.encode({"op": "log", "params": [timestamp, `[Client#${clientID}]`, ...args]}));
    }
    const originalWarn = console.warn;
    console.warn = function(...args) {
        const timestamp = formatCustom(new Date());
        originalWarn.apply(console, [timestamp, ...args]);
        socket.send(msgpack.encode({"op": "warn", "params": [timestamp, `[Client#${clientID}]`, ...args]}));
    }
    const originalError = console.error;
    console.error = function(...args) {
        const timestamp = formatCustom(new Date());
        originalError.apply(console, [timestamp, ...args]);
        socket.send(msgpack.encode({"op": "error", "params": [timestamp, `[Client#${clientID}]`, ...args]}));
    }
    //Error handling
    window.onerror = function(msg, src, line, col, err) {
        const div = document.getElementById("errorlog");
        if (div) div.innerText += `ERROR: ${msg}\n  at ${src}:${line}:${col}\n`;
        const timestamp = formatCustom(new Date());
        //originalError.apply(console, [timestamp, ...args]);
        socket.send(msgpack.encode({"op": "error", "params": [timestamp, `[Client#${clientID}]`, `ERROR: ${msg}\n  at ${src}:${line}:${col}\n`]}));
        return false;
    };
    window.onunhandledrejection = function(e) {
        const div = document.getElementById("errorlog");
        if (div) div.innerText += `UNHANDLED PROMISE: ${e.reason}\n`;
        //originalError.apply(console, [timestamp, ...args]);
        socket.send(msgpack.encode({"op": "error", "params": [timestamp, `[Client#${clientID}]`, `UNHANDLED PROMISE: ${e.reason}\n`]}));
    };
}

function onModsReady() {
    // -- Hand off WebSocket to mod dispatch table ------------------------------
    // From this point all messages are routed through wsDispatch
    // which mod client.js files have populated during load_mod_js
    socket.onmessage = (e) => {
        const msg = msgpack.decode(new Uint8Array(e.data));
        const handler = wsDispatch[msg["op"]];
        if (handler) {
            for (let i=0;i<handler.length;i++) handler[i](msg["params"]);
        } else {
            console.warn("Backend attempted to access unknown frontend handler " + msg["op"]+" with params "+msg["params"]+".");
        }
    }
    // -- Trigger first mod op -------------------------------------------------
    socket.send(msgpack.encode({"op": "syncBlocks", "params": []}));
}