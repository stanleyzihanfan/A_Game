/**
 * Central WebSocket op handler registry
 * Replaces the wsDispatch dict in the original backend.py
 * Mods call register_handler() to add their own ops
 */
class Registry {
    constructor() {
        this._handlers = { "main:tick": {} };
        this.UFID=0;
    }

    /**
     * Register a handler
     *
     * @param {string} op - Name of event hook
     * @param {Function} func - Function object of handler
     * @param {string} [name] - Name of handler function
     */
    register_handler(op, func, name = null) {
        let handlerName = name;
        // Create new event hook if not created
        if (!Object.hasOwn(this._handlers,op)){
            this._handlers[op] = {};
            console.log(`  Frontend Event Hook ${op} created.`);
        }
        // If name is not provided, replace with _lambda+unique function ID to prevent collision
        if (handlerName === null) {
            handlerName = `_lambda_${this.UFID}`;
            this.UFID++;
        }
        // Warn if another handler with the same name already exists
        if (Object.hasOwn(this._handlers[op],handlerName)){
            console.warn(`  Handler ${handlerName} already registered under ${op}, overwriting!`);
        }
        // Register function in _handlers
        this._handlers[op][handlerName] = func;
        console.log(`    New handler ${handlerName} registered under ${op}.`);
    }

    /**
     * Get a handler
     *
     * @param {string} op - Event hook to look under
     * @param {string} [name] - Optional, name of handler to get
     * @returns {Function|Object|null} If name is provided, returns specified handler function.
     * If name is not provided/None, returns full event hook of handler+name as an object.
     * Returns null if not found.
     */
    get_handler(op, name = null) {
        if (name && Object.hasOwn(this._handlers,op)){
            return this._handlers[op][name] || null;
        }
        return this._handlers[op] || null;
    }

    /**
     * Dispatch a hook/handler
     *
     * @param {string} op - Event hook to dispatch
     * @param {GameState} gameState - The game state to pass to handlers
     */
    dispatch(op, gameState) {
        const handlers = this.get_handler(op);
        if (handlers) {
            for (const [handlerName, func] of Object.entries(handlers)){
                try{
                    func(gameState, this);
                } catch (e) {
                    console.error(`Handler '${handlerName}' under '${op}' failed:`);
                    console.error(`    ${e.name}: ${e.message}`);
                    throw e;
                }
            }
        }else{
            console.warn(`Attempted to access unknown frontend handler ${op}.`);
        }
    }
}