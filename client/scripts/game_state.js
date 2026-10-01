/**
 * Central game state storage and accessing handler.
 *
 * Mirrors the server-side GameState API so mod logic can stay consistent
 * on both ends. Keys are arrays (e.g. ["players", "Alice", "pos"]).
 *
 * Namespacing:
 * The FIRST element of a key decides its namespace. Mods get automatic
 * namespacing through the same active-namespace mechanism as the Registry:
 * while a mod's script runs (during mod loading), any UNQUALIFIED key — one
 * whose first element contains no ":" — is prefixed with that mod's
 * manifest namespace. Keys whose first element already contains ":"
 * (e.g. ["core:initialized"]) pass through untouched, so core keys stay
 * hard-coded.
 */
class GameState {
    constructor() {
        this._state = {};
        // Stack of active mod namespaces (mirrors Registry._namespaceStack).
        // Empty means "not inside mod code" — unqualified keys then reference
        // core game data as before, preserving existing behavior.
        this._namespaceStack = [];
    }

    // -- Namespace management ---------------------------------------------------
    /**
     * Enter a mod's namespace. The mod loader calls this around eval() of a
     * mod's client script.
     * @param {string} namespace - Namespace string from the mod's manifest.json
     */
    pushNamespace(namespace) {
        this._namespaceStack.push(namespace);
    }

    /**
     * Leave the most recently pushed namespace.
     */
    popNamespace() {
        if (this._namespaceStack.length) this._namespaceStack.pop();
    }

    /**
     * Return the active namespace, or null if not inside mod code.
     * @returns {string|null}
     */
    currentNamespace() {
        return this._namespaceStack.length ? this._namespaceStack[this._namespaceStack.length - 1] : null;
    }

    /**
     * Prefix an unqualified key's first element with the active namespace.
     *
     * A key is unqualified if its first element contains no ":". Qualified
     * keys (e.g. ["core:initialized"]) are returned unchanged — this is
     * what keeps all "core:something" usages working as before.
     *
     * @param {Array} key - Key array to resolve
     * @returns {Array} New key array with first element namespaced if unqualified
     */
    _resolve(key) {
        if (!Array.isArray(key) || key.length === 0) return key;
        if (String(key[0]).includes(":")) return key;
        const namespace = this.currentNamespace();
        if (namespace === null) return key;
        return [`${namespace}:${key[0]}`, ...key.slice(1)];
    }

    /**
     * Sets a key-value pair to game state
     *
     * Unqualified keys are auto-namespaced with the active mod namespace.
     *
     * @param {Array} key - Key to add
     * @param {*} value - Value to add
     * @param {boolean} [override=false] - Whether to override any conflicting leaves
     */
    set(key, value, override = false) {
        key = this._resolve(key);
        let last = this._state;
        for (let i = 0; i < key.length - 1; i++) {
            const k = key[i];
            if (!(k in last) || typeof last[k] !== 'object' || last[k]===null || Array.isArray(last[k])){
                if (k in last && !override){
                    throw new Error(`Key ${key} does not exist in game state`);
                }
                last[k]={};
            }
            last = last[k];
        }
        last[key[key.length - 1]] = value;
    }

    /**
     * Gets value for key
     *
     * Unqualified keys are auto-namespaced with the active mod namespace.
     *
     * @param {Array} key - Key to get value for
     * @param {*} [defaultVal=true] - Default value
     * @returns {*} Returns value if key exists, else returns default
     */
    get(key,defaultVal=null) {
        key = this._resolve(key);
        let last = this._state;
        for (const k of key) {
            if (typeof last !== 'object' || last === null || !(k in last)) {
                return defaultVal;
            }
            last = last[k];
        }
        if (last===undefined) return defaultVal;
        return JSON.parse(JSON.stringify(last));
    }

    /**
     * Get if a key exists
     *
     * Unqualified keys are auto-namespaced with the active mod namespace.
     *
     * @param {Array} key - Key to check
     * @returns {boolean} Boolean if key exists or not
     */
    exists(key) {
        key = this._resolve(key);
        let last = this._state;
        for (const k of key) {
            if (typeof last !== 'object' || last === null || !(k in last)) {
                return false;
            }
            last = last[k];
        }
        return true;
    }

    /**
     * Helper function to initialize a value if it does not exist, else do nothing
     * @param {Array} key - key to initialize
     * @param {*} value - Value to initialize to
     */
    initialize(key, value){
        if (!this.exists(key))
            this.set(key,value,true);
    }

    /**
     * Helper to return if key is pressed from gamestate
     * @param {string} code key to look for
     * @returns Boolean value representing if key is pressed
     */
    isKeyDown(code){
        return this.get(["core:keys",code],false);
    }

    // -- Send/receive buffer helpers --------------------------------------------
    // These wrap the client sync buffers so mods never have to touch raw
    // "core:*" keys themselves. The buffers themselves live under fixed
    // internal keys (created by main.js/initialization.js outside mod code),
    // so these helpers access them explicitly and only the MESSAGE KEYS
    // inside the buffers get auto-namespaced with the active mod namespace.
    /**
     * Add a key-value pair to the send buffer for this tick.
     *
     * The buffer is sent to the server once per tick and then cleared. The
     * key is namespaced automatically ("mydata" -> "mymod:mydata"), so a mod
     * can never collide with another mod's send keys.
     * @param {string} key - Unqualified key to send under
     * @param {*} value - Value to send
     */
    addToSendBuffer(key, value) {
        const nsKey = this._resolveSingle(key);
        // Read the buffer WITHOUT namespace resolution — it is core data
        let sendbuffer = this._rawGet(["core:client_send_buffer"]);
        if (typeof sendbuffer !== 'object' || sendbuffer === null) {
            sendbuffer = {};
            this._rawSet(["core:client_send_buffer"], sendbuffer, true);
        }
        sendbuffer[nsKey] = value;
        this._rawSet(["core:client_send_buffer"], sendbuffer);
    }

    /**
     * Read this mod's messages from the server receive buffer.
     *
     * Each tick the server pushes one payload dict per sync message; this
     * helper collects the values stored under this mod's namespaced key
     * across all buffered messages of the current tick.
     * @param {string} [key] - Unqualified key to read (defaults to every
     *                         key under this mod's namespace)
     * @returns {Array} List of values received for that key this tick
     */
    readServerMessages(key = null) {
        const ns = this.currentNamespace();
        const prefix = ns === null ? "" : `${ns}:`;
        const target = key === null ? null : `${prefix}${key}`;
        const out = [];
        // Read the buffer WITHOUT namespace resolution — it is core data
        const buffer = this._rawGet(["core:server_receive_buffer"]);
        if (!Array.isArray(buffer)) return out;
        for (const data of buffer) {
            if (typeof data !== 'object' || data === null) continue;
            for (const [k, v] of Object.entries(data)) {
                if (target === null) {
                    if (prefix === "" || k.startsWith(prefix)) out.push({ [k]: v });
                } else if (k === target) {
                    out.push(v);
                }
            }
        }
        return out;
    }

    /**
     * Internal: raw get/set that bypass namespace resolution entirely.
     * Used by the buffer helpers, which must always hit the core buffer
     * locations no matter which mod is calling.
     */
    _rawGet(key, defaultVal = null) {
        let last = this._state;
        for (const k of key) {
            if (typeof last !== 'object' || last === null || !(k in last)) {
                return defaultVal;
            }
            last = last[k];
        }
        if (last === undefined) return defaultVal;
        return last;
    }

    _rawSet(key, value, override = false) {
        let last = this._state;
        for (let i = 0; i < key.length - 1; i++) {
            const k = key[i];
            if (!(k in last) || typeof last[k] !== 'object' || last[k]===null || Array.isArray(last[k])){
                if (k in last && !override){
                    throw new Error(`Key ${key} does not exist in game state`);
                }
                last[k]={};
            }
            last = last[k];
        }
        last[key[key.length - 1]] = value;
    }

    /**
     * Internal: resolve a single string key (not a key array) to its
     * namespaced form.
     * @param {string} key
     * @returns {string}
     */
    _resolveSingle(key) {
        if (typeof key !== 'string' || key.includes(":")) return key;
        const namespace = this.currentNamespace();
        if (namespace === null) {
            throw new Error(
                `Cannot use unqualified key '${key}' outside of mod code — ` +
                `message keys must be namespaced (e.g. 'mymod:${key}')`
            );
        }
        return `${namespace}:${key}`;
    }
}