/**
 * Central WebSocket op handler registry
 * Replaces the wsDispatch dict in the original backend.py
 * Mods call register_handler() to add their own ops
 *
 * Namespacing:
 * The registry tracks an "active namespace" (set by the mod loader around a
 * mod script's eval()). Any unqualified op or handler name (no ":") is
 * automatically prefixed with it: "syncBlocks" -> "testmod:syncBlocks".
 * Strings that already contain ":" (e.g. every "core:something") pass through
 * untouched. While no mod is loading (namespace null), unqualified names are
 * an error.
 */
class Registry {
    constructor() {
        this._handlers = { "core:tick": {} ,"core:keydown":{}, "core:keyup":{}};
        this.UFID=0;
        // Stack of active namespaces; top frames the mod currently loading.
        this._namespaceStack = [];
    }

    // -- Namespace management ---------------------------------------------------
    /**
     * Enter a mod's namespace. The mod loader calls this before eval()ing a
     * mod's client script, popNamespace() after.
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
     * Return the active namespace, or null if not inside mod loading.
     * @returns {string|null}
     */
    currentNamespace() {
        return this._namespaceStack.length ? this._namespaceStack[this._namespaceStack.length - 1] : null;
    }

    /**
     * Prefix an unqualified name with the active namespace.
     *
     * Strings that already contain ":" (e.g. "core:tick") are returned
     * unchanged. Qualified strings with a foreign namespace are also kept
     * as-is — cross-namespace references are allowed.
     *
     * @param {string} name - Op or handler name to resolve
     * @returns {string} Fully-qualified name
     * @throws {Error} If name is unqualified and no namespace is active
     */
    _resolve(name) {
        if (name === null || name === undefined) return name;
        if (name.includes(":")) return name;
        const namespace = this.currentNamespace();
        if (namespace === null) {
            throw new Error(
                `Cannot use unqualified name '${name}' outside of mod loading — ` +
                `ops and handler names must be namespaced (e.g. 'mymod:${name}')`
            );
        }
        return `${namespace}:${name}`;
    }

    /**
     * Register a handler.
     *
     * Unqualified op/handler names are automatically prefixed with the
     * namespace of the mod being loaded. The handler remembers the namespace
     * active at registration, and dispatch() re-enters it while the handler
     * runs — so the handler's own unqualified names/keys keep resolving to its
     * mod's namespace even when dispatched long after loading.
     *
     * @param {string} op - Name of event hook
     * @param {Function} func - Function object of handler
     * @param {string} [name] - Name of handler function
     */
    // -- Handler registration ------------------------------------------------------
    // The main API mods use at load time to declare their handlers.
    register_handler(op, func = null, name = null) {
        // Capture the namespace active at registration (null for core code)
        const handlerNamespace = this.currentNamespace();
        op = this._resolve(op);
        if (name !== null) name = this._resolve(name);
        let handlerName = name;
        // Create new event hook if not created
        if (!Object.hasOwn(this._handlers,op)){
            this._handlers[op] = {};
            console.log(`  Frontend Event Hook ${op} created.`);
        }
        // Exit early if no function is provided (only registers event hook)
        if (func === null) return;
        // If name is not provided, use a unique id to prevent collision
        if (handlerName === null) {
            handlerName = `_lambda_${this.UFID}`;
            this.UFID++;
        }
        // Warn if another handler with the same name already exists
        if (Object.hasOwn(this._handlers[op],handlerName)){
            console.warn(`  Handler ${handlerName} already registered under ${op}, overwriting!`);
        }
        // Register function in _handlers
        this._handlers[op][handlerName] = { func, namespace: handlerNamespace };
        console.log(`    New handler ${handlerName} registered under ${op}.`);
    }

    /**
     * Remove a handler registered under an op.
     *
     * The mirror of register_handler(): same (op, name) pair, one removes what
     * the other installs. This is how an addon mod disables a handler owned by
     * another mod — register_handler() can only REPLACE one, and replacing is
     * not the same as removing (you would have to supply a substitute with a
     * compatible signature).
     *
     * Names are the contract. Because a handler's fully-qualified name is
     * stable and visible (`get_handler(op)` returns the whole op's dict, so the
     * registered names can be read at runtime), an addon does not need
     * namespace filtering to find its target: it names it directly, e.g.
     * `unregister_handler("core:tick", "player_position:movement_handler")`.
     *
     * The op is resolved through the active namespace exactly as
     * register_handler() resolves it, so pass the op in the same form you
     * registered it under ("core:tick" passes through untouched).
     *
     * Returns boolean rather than throwing, because the realistic failure is
     * "you targeted the wrong name" and a silent no-op would hide exactly the
     * bug that name-based targeting makes likely. Check the return value.
     *
     * @param {string} op - Name of event hook
     * @param {string} name - Name of handler to remove
     * @returns {boolean} True if a handler was removed, false if the op or name
     * was not registered.
     */
    unregister_handler(op, name) {
        op = this._resolve(op);
        if (name === null || name === undefined) return false;
        name = this._resolve(name);
        const handlers = this._handlers[op];
        if (!handlers || !Object.hasOwn(handlers, name)) return false;
        delete handlers[name];
        console.log(`    Handler ${name} removed from ${op}.`);
        return true;
    }

    /**
     * Get a handler.
     *
     * @param {string} op - Event hook to look under
     * @param {string} [name] - Optional, name of handler to get
     * @returns {Object|Function|null} If name is provided, returns the handler
     * record {func, namespace} (use .func for the callable).
     * If name is not provided/None, returns full event hook of handler+name as
     * an object. Returns null if not found.
     */
    // -- Handler retrieval ----------------------------------------------------------
    // Looks up a handler record (or a whole op's object) by name.
    get_handler(op, name = null) {
        op = this._resolve(op);
        if (name !== null) name = this._resolve(name);
        if (name && Object.hasOwn(this._handlers,op)){
            return this._handlers[op][name] || null;
        }
        return this._handlers[op] || null;
    }

    /**
     * Dispatch a hook/handler.
     *
     * Dispatch intentionally does NOT auto-namespace the op itself: op is used
     * as given. But each handler is invoked inside the namespace it was
     * registered under (null for core code), so its own unqualified names/keys
     * resolve to its mod's namespace at runtime.
     *
     * @param {string} op - Event hook to dispatch
     * @param {GameState} gameState - The game state to pass to handlers
     */
    // -- Dispatch -------------------------------------------------------------------
    // Runs every handler registered under an op, each inside the namespace it was
    // registered under, passing the game state and registry to the handler.
    //
    // IMPORTANT — the snapshot is load-bearing. Object.entries() copies the keys
    // into an array up front, so a handler that calls unregister_handler() (on
    // itself or another handler) while this loop is running cannot corrupt the
    // iteration: the loop walks the list as it was when dispatch began. Do NOT
    // "optimise" this into `for (const k in handlers)` or a live
    // Object.keys() lookup per step — that would turn a mid-dispatch
    // unregister into skipped handlers (and, historically, the exact class of
    // bug that makes removals look unreliable).
    dispatch(op, gameState) {
        const handlers = this.get_handler(op);
        if (handlers) {
            for (const [handlerName, record] of Object.entries(handlers)){
                const func = record.func;
                const namespace = record.namespace;
                if (namespace !== null) {
                    this.pushNamespace(namespace);
                    if (gameState && typeof gameState.pushNamespace === "function") {
                        gameState.pushNamespace(namespace);
                    }
                    if (typeof uiRegistry !== "undefined" && uiRegistry && typeof uiRegistry.pushNamespace === "function") {
                        uiRegistry.pushNamespace(namespace);
                    }
                }
                try{
                    func(gameState, this);
                } catch (e) {
                    console.error(`Handler '${handlerName}' under '${op}' failed:`);
                    console.error(`    ${e.name}: ${e.message}`);
                    e.handled=true;
                    throw e;
                } finally {
                    if (namespace !== null) {
                        this.popNamespace();
                        if (gameState && typeof gameState.popNamespace === "function") {
                            gameState.popNamespace();
                        }
                        if (typeof uiRegistry !== "undefined" && uiRegistry && typeof uiRegistry.popNamespace === "function") {
                            uiRegistry.popNamespace();
                        }
                    }
                }
            }
        }
    }
}