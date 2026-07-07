// Assuming GameState is imported from the appropriate module
import {GameState} from './game_state.js';

/**
 * Central WebSocket op handler registry
 * Replaces the wsDispatch dict in the original backend.py
 * Mods call register_handler() to add their own ops
 */
class Registry {
    constructor() {
        this._handlers = { tick: {} };
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
        if (!(op in this._handlers)) {
            this._handlers[op] = {};
            console.log(`    Event Hook ${op} created.`);
        }
        // If name is not provided, replace with _lambda+unique function ID to prevent collision
        if (handlerName === null) {
            handlerName = `_lambda_${Registry._getFunctionId(func)}`;
        }
        // Warn if another handler with same name already exists
        if (handlerName in this._handlers[op]) {
            console.warn(`    [WARN] Handler ${handlerName} already registered under ${op}, overwriting!`);
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
        if (name && op in this._handlers) {
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
            for (const [handlerName, func] of Object.entries(handlers)) {
                try {
                    func(gameState, this);
                } catch (e) {
                    console.error(`Handler '${handlerName}' under '${op}' failed:`);
                    console.error(`    ${e.name}: ${e.message}`);
                    throw e;
                }
            }
        } else {
            console.error(`Frontend attempted to access unknown handler ${op}`);
        }
    }

    // Helper to generate a unique ID for a function (since JS doesn't have id())
    static _getFunctionId(func) {
        if (!func._funcId) {
            func._funcId = Registry._nextFuncId++;
        }
        return func._funcId;
    }
}
Registry._nextFuncId = 1;

