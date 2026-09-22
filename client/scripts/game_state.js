/**
 * Central game state storage and accessing handler.
 *
 * Mirrors the server-side GameState API so mod logic can stay consistent
 * on both ends. Keys are arrays (e.g. ["players", "Alice", "pos"]).
 */
class GameState {
    constructor() {
        this._state = {};
    }

    /**
     * Sets a key-value pair to game state
     * 
     * @param {Array} key - Key to add
     * @param {*} value - Value to add
     * @param {boolean} [override=false] - Whether to override any conflicting leaves
     */
    set(key, value, override = false) {
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
     * @param {Array} key - Key to get value for
     * @param {*} [defaultVal=true] - Default value
     * @returns {*} Returns value if key exists, else returns default
     */
    get(key,defaultVal=null) {
        let last = this._state;
        for (const k of key) {
            if (typeof last !== 'object' || last === null || !(k in last)) {
                return null;
            }
            last = last[k];
        }
        if (last===undefined) return defaultVal;
        return JSON.parse(JSON.stringify(last));
    }

    /**
     * Get if a key exists
     * 
     * @param {Array} key - Key to check
     * @returns {boolean} Boolean if key exists or not
     */
    exists(key) {
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
     * @param {*} value - value to initialize to
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
        return this.get(["keys",code],false);
    }
}