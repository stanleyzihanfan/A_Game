/**
 * Central client-side UI registry.
 *
 * Mirrors the Registry (client_ws_registry.js) and GameState (game_state.js)
 * design so mods can create and edit UI the same way they already create
 * handlers and game state:
 *
 *   - Every mod gets an automatic namespace (from manifest.json). While a mod's
 *     client script is eval()'d, the loader pushes that namespace onto this
 *     registry, so any UNQUALIFIED ui name (one with no ":") is prefixed with
 *     the mod's namespace ("panel" -> "ui_demo:panel"). "core:..." strings pass
 *     through untouched, exactly like wsRegistry / gameState.
 *   - Views, event handlers, and styles are registered by name, stored in
 *     dictionaries keyed by the fully-qualified name, and can be looked up /
 *     mounted / dispatched later.
 *   - A view builder can be a function returning a DOM node or an HTML string;
 *     the registry mounts it into a container (default #ui-root) and remembers
 *     the instance for later lookup and teardown.
 *   - Event handlers are dispatched the same way as wsRegistry: dispatch()
 *     re-enters the namespace the handler was registered under, so the handler's
 *     own unqualified ui names and game-state keys keep resolving to its mod's
 *     namespace at runtime.
 *
 * There is currently NO automatic client-side lifecycle hook (the server has
 * core:on_player_disconnect but the client has no parallel), so unmountAll()
 * is available for mods/core to tear down every view on their own terms.
 */
class UIRegistry {
    constructor() {
        // Fully-qualified name -> { buildFn, namespace, opts }
        this._views = {};
        // Fully-qualified name -> array of mounted elements
        this._instances = {};
        // Fully-qualified event -> { handlerName: { func, namespace } }
        this._handlers = {};
        // List of injected <style> ids, for cleanup
        this._styles = [];
        this._uid = 0;
        // Stack of active mod namespaces (mirrors Registry / GameState).
        // Empty means "not inside mod code" — unqualified names then error.
        this._namespaceStack = [];
        // Default mount container (#ui-root in frontend.html). Cached; may be
        // swapped with setRoot().
        this._root = null;
    }

    // -- Namespace management ---------------------------------------------------
    /**
     * Enter a mod's namespace. The mod loader calls this around eval() of a
     * mod's client script, matching wsRegistry / gameState.
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
     * Prefix an unqualified ui name with the active namespace.
     *
     * A name is unqualified if it contains no ":". Qualified names
     * (e.g. "core:...") are returned unchanged.
     *
     * @param {string} name - Ui name to resolve
     * @returns {string} Fully-qualified name
     * @throws {Error} If name is unqualified and no namespace is active
     */
    _resolve(name) {
        if (name === null || name === undefined) return name;
        if (typeof name !== "string") return name;
        if (name.includes(":")) return name;
        const namespace = this.currentNamespace();
        if (namespace === null) {
            throw new Error(
                `Cannot use unqualified UI name '${name}' outside of mod code — ` +
                `ui names must be namespaced (e.g. 'mymod:${name}')`
            );
        }
        return `${namespace}:${name}`;
    }

    // -- Mount root -------------------------------------------------------------
    /**
     * Return the default mount container. Reuses #ui-root if it exists; lazily
     * re-queries it so it works even before the DOM is fully parsed.
     * @returns {HTMLElement|null}
     */
    getRoot() {
        if (this._root && this._root.isConnected) return this._root;
        this._root = document.getElementById("ui-root");
        return this._root;
    }

    /**
     * Override the default mount container.
     * @param {HTMLElement|null} el
     */
    setRoot(el) {
        this._root = el;
    }

    // -- View registration ------------------------------------------------------
    /**
     * Register a UI view builder under a (possibly unqualified) name.
     *
     * The builder is called lazily on mount() with (ui, args, container) and
     * may return a DOM node or an HTML string. The namespace active at
     * registration is captured and re-entered on mount, so any unqualified
     * ui names the builder uses keep resolving to this mod's namespace.
     *
     * @param {string} name - View name (auto-prefixed with active namespace)
     * @param {(ui:UIRegistry, args:any, container:HTMLElement)=>Node|string} buildFn
     * @param {object} [opts] - Optional extra metadata for the view
     * @returns {string} Fully-qualified name
     */
    register_view(name, buildFn, opts = {}) {
        const resolved = this._resolve(name);
        const namespace = this.currentNamespace();
        if (Object.hasOwn(this._views, resolved)) {
            console.warn(`  UI view '${resolved}' already registered, overwriting!`);
        }
        this._views[resolved] = { buildFn, namespace, opts };
        console.log(`    UI view '${resolved}' registered.`);
        return resolved;
    }

    /**
     * Look up a registered view record.
     * @param {string} name
     * @returns {object|null} The {buildFn, namespace, opts} record, or null.
     */
    get_view(name) {
        const resolved = this._resolve(name);
        return this._views[resolved] || null;
    }

    /**
     * Whether a view is registered under the (possibly qualified) name.
     * @param {string} name
     * @returns {boolean}
     */
    has(name) {
        return !!this.get_view(name);
    }

    /**
     * Create an instance of a registered view and append it to a container.
     *
     * The builder runs with the view's namespace re-entered, so any
     * unqualified ui names it uses resolve to the mod's namespace.
     *
     * @param {string} name - View name (resolved through active namespace)
     * @param {HTMLElement|string|null} [target] - Container element or CSS selector; defaults to #ui-root
     * @param {any} [args] - Value forwarded to the builder
     * @returns {Node|null} The created element, or null if the view/container is missing
     */
    mount(name, target = null, args = null) {
        const resolved = this._resolve(name);
        const rec = this._views[resolved];
        if (!rec) {
            console.warn(`  UI view '${resolved}' is not registered — call register_view() first.`);
            return null;
        }
        const container = target
            ? (typeof target === "string" ? document.querySelector(target) : target)
            : this.getRoot();
        if (!container) {
            console.warn(`  Cannot mount UI view '${resolved}': no target (no #ui-root in the DOM).`);
            return null;
        }
        this.pushNamespace(rec.namespace);
        try {
            const built = rec.buildFn(this, args, container);
            const el = this._toNode(built, container);
            if (el && el.nodeType) {
                container.appendChild(el);
                if (!Object.hasOwn(this._instances, resolved)) this._instances[resolved] = [];
                this._instances[resolved].push(el);
            }
            return el;
        } finally {
            this.popNamespace();
        }
    }

    /**
     * Remove every mounted instance of a view.
     * @param {string} name - View name (resolved through active namespace)
     */
    unmount(name) {
        const resolved = this._resolve(name);
        const els = this._instances[resolved];
        if (!els) return;
        for (const el of els) {
            if (el && el.parentNode) el.parentNode.removeChild(el);
        }
        this._instances[resolved] = [];
    }

    /**
     * Tear down every view this registry has mounted. No lifecycle hook exists
     * on the client, so this is how mods/core can clean up after themselves.
     */
    unmountAll() {
        for (const key of Object.keys(this._instances)) {
            this.unmount(key);
        }
    }

    /**
     * Get the most recently mounted element for a view.
     * @param {string} name - View name (resolved through active namespace)
     * @returns {Node|null}
     */
    get_el(name) {
        const resolved = this._resolve(name);
        const els = this._instances[resolved];
        return els && els.length ? els[els.length - 1] : null;
    }

    /**
     * Get all mounted elements for a view.
     * @param {string} name - View name (resolved through active namespace)
     * @returns {Node[]}
     */
    get_instances(name) {
        const resolved = this._resolve(name);
        return this._instances[resolved] || [];
    }

    /**
     * Normalize a builder result to a Node. Strings are parsed as HTML via a
     * <template>; the first element child is returned (a view should have a
     * single root element).
     * @param {Node|string|*} built
     * @param {HTMLElement} container
     * @returns {Node|*}
     */
    _toNode(built, container) {
        if (built instanceof Node) return built;
        if (typeof built === "string") {
            const tpl = document.createElement("template");
            tpl.innerHTML = built.trim();
            return tpl.content.firstElementChild;
        }
        return built;
    }

    // -- Event handlers ---------------------------------------------------------
    /**
     * Register a UI event handler, mirroring Registry.register_handler.
     * The event name and optional handler name are auto-prefixed with the
     * active namespace. The namespace active at registration is captured and
     * re-entered on dispatch().
     *
     * @param {string} event - Event hook name
     * @param {Function} func - Handler function
     * @param {string} [name] - Optional handler name
     * @returns {string} The (resolved) handler name
     */
    on(event, func, name = null) {
        const ev = this._resolve(event);
        const namespace = this.currentNamespace();
        let handlerName = name;
        if (handlerName !== null) handlerName = this._resolve(handlerName);
        if (!Object.hasOwn(this._handlers, ev)) {
            this._handlers[ev] = {};
            console.log(`  Frontend UI Event Hook ${ev} created.`);
        }
        if (handlerName === null) {
            handlerName = `_ui_${this._uid}`;
            this._uid++;
        }
        if (Object.hasOwn(this._handlers[ev], handlerName)) {
            console.warn(`  UI handler ${handlerName} already registered under ${ev}, overwriting!`);
        }
        this._handlers[ev][handlerName] = { func, namespace };
        console.log(`    UI handler ${handlerName} registered under ${ev}.`);
        return handlerName;
    }

    /**
     * Look up a UI event handler or whole event hook.
     * @param {string} event
     * @param {string} [name]
     * @returns {object|Function|null}
     */
    get(event, name = null) {
        const ev = this._resolve(event);
        if (name !== null) {
            const n = this._resolve(name);
            return this._handlers[ev]?.[n] || null;
        }
        return this._handlers[ev] || null;
    }

    /**
     * Dispatch a UI event to its registered handlers, each inside the namespace
     * it was registered under (and, if gameState is given, that too). Mirrors
     * Registry.dispatch.
     *
     * @param {string} event - Event hook to dispatch
     * @param {*} [payload] - Value passed to each handler
     * @param {GameState} [gameState] - Optional game state to namespace alongside
     */
    dispatch(event, payload = null, gameState = null) {
        const ev = this._resolve(event);
        const handlers = this._handlers[ev];
        if (!handlers) return;
        for (const [handlerName, record] of Object.entries(handlers)) {
            const namespace = record.namespace;
            if (namespace !== null) {
                this.pushNamespace(namespace);
                if (gameState && typeof gameState.pushNamespace === "function") {
                    gameState.pushNamespace(namespace);
                }
            }
            try {
                record.func(payload, this, gameState);
            } catch (e) {
                console.error(`UI handler '${handlerName}' under '${ev}' failed:`);
                console.error(`    ${e.name}: ${e.message}`);
                e.handled = true;
                throw e;
            } finally {
                if (namespace !== null) {
                    this.popNamespace();
                    if (gameState && typeof gameState.popNamespace === "function") {
                        gameState.popNamespace();
                    }
                }
            }
        }
    }

    // -- Styles -----------------------------------------------------------------
    /**
     * Inject a <style> element and remember its id for cleanup. Calling again
     * with the same id replaces the content instead of duplicating.
     *
     * @param {string} cssText - CSS rules
     * @param {string} [id] - Optional explicit id; default is a generated one
     * @returns {string} The style element's id
     */
    register_style(cssText, id = null) {
        const namespace = this.currentNamespace();
        const styleId = id || `ui-style-${this._uid++}`;
        let el = document.getElementById(styleId);
        if (!el) {
            el = document.createElement("style");
            el.id = styleId;
            el.setAttribute("data-ui-namespace", namespace || "");
            document.head.appendChild(el);
        }
        el.textContent = cssText;
        if (this._styles.indexOf(styleId) === -1) this._styles.push(styleId);
        return styleId;
    }

    /**
     * Remove every style element this registry injected.
     */
    clearStyles() {
        for (const id of this._styles) {
            const el = document.getElementById(id);
            if (el) el.remove();
        }
        this._styles = [];
    }

    /**
     * Run fn with a namespace re-entered for its duration, then restore it.
     * This is the runtime-safe primitive behind the bound handles: most UI work
     * happens AFTER the mod's initial eval(), when the namespace stack is empty.
     * _withNamespace pushes the captured namespace so unqualified ui names used
     * inside fn still resolve to the right mod, then pops it back.
     * @param {string|null} namespace
     * @param {Function} fn
     * @returns {*}
     */
    _withNamespace(namespace, fn) {
        if (namespace !== null && namespace !== undefined) this.pushNamespace(namespace);
        try {
            return fn();
        } finally {
            if (namespace !== null && namespace !== undefined) this.popNamespace();
        }
    }

    /**
     * Create a bound UI view handle.
     *
     * This is the runtime-safe way to build UI. You register and get a handle
     * while your mod's namespace is active (during eval). The handle captures
     * that namespace, so every method you call on it later — mount(), update(),
     * set(), on(), unmount() — works even after the namespace stack is empty,
     * because each call re-enters the captured namespace internally.
     *
     * Callers should hold the returned handle and mutate it during gameplay
     * instead of re-resolving names at runtime.
     *
     * @param {string} name - View name (resolved against the active namespace now)
     * @param {(ui:UIRegistry, args:any, container:HTMLElement)=>Node|string} buildFn
     * @param {object} [opts]
     * @returns {object} A bound handle { el, name, mount, update, set, on, unmount }
     */
    createView(name, buildFn, opts = {}) {
        const resolved = this._resolve(name);
        const ns = this.currentNamespace();
        if (!Object.hasOwn(this._views, resolved)) {
            this._views[resolved] = { buildFn, namespace: ns, opts };
        }
        const reg = this;
        const handle = {
            el: null,
            name: resolved,
            // Create/mount an instance (into #ui-root or a custom target).
            mount(target = null, args = null) {
                return reg._withNamespace(ns, () => {
                    handle.el = reg.mount(resolved, target, args);
                    return handle.el;
                });
            },
            // Run a caller callback with this view's element, in the mod's namespace.
            update(fn) {
                return reg._withNamespace(ns, () => fn(handle.el, reg));
            },
            // Set the textContent of the first element matching a CSS selector.
            set(selector, value) {
                return reg._withNamespace(ns, () => {
                    if (!handle.el) return null;
                    const el = handle.el.querySelector(selector);
                    if (el) el.textContent = value;
                    return el;
                });
            },
            // Attach a DOM event listener to an element inside the view.
            on(selector, event, fn) {
                return reg._withNamespace(ns, () => {
                    if (!handle.el) return null;
                    const el = handle.el.querySelector(selector);
                    if (el) el.addEventListener(event, fn);
                    return el;
                });
            },
            // Remove every mounted instance of this view.
            unmount() {
                return reg._withNamespace(ns, () => reg.unmount(resolved));
            },
        };
        return handle;
    }

    /**
     * Bind a UI event to this mod's namespace.
     *
     * Returns a function that, when called later (from a click, timer, etc.),
     * dispatches the event with this mod's namespace re-entered. Use the
     * returned closure as the DOM listener instead of calling dispatch()
     * directly, so unqualified names resolve at runtime.
     *
     * The handlers for the event are registered separately with on(); bindEvent
     * only captures the event + namespace and produces a safe dispatcher.
     *
     * @param {string} event - Event hook (resolved against the active namespace now)
     * @returns {Function} (...args) => this.dispatch(event, ...args) in the mod's namespace
     */
    bindEvent(event) {
        const ev = this._resolve(event);
        const ns = this.currentNamespace();
        return (...args) => {
            return this._withNamespace(ns, () => this.dispatch(ev, ...args));
        };
    }

    /**
     * Resolve a name now and return its fully-qualified form, so a caller can
     * use it at runtime without relying on a live namespace on the stack.
     * @param {string} name
     * @returns {string} Fully-qualified name
     */
    bindName(name) {
        return this._resolve(name);
    }
}

// -- Instance + global exposure --------------------------------------------------
// Bootstrap scripts (pre_initialization.js, main.js) are classic <script> tags, so
// a top-level `const` here becomes a global lexical binding visible as a bare
// identifier to later scripts AND to eval()'d mod code (same trick as wsRegistry /
// gameState). We also attach it to `window` (like window.renderer in scene_setup)
// so the ws Registry can re-enter its namespace at dispatch time even though the
// Registry source was loaded before this file.
const uiRegistry = new UIRegistry();
window.uiRegistry = uiRegistry;
// Convenience alias mods can use in templates/builders.
window.ui = uiRegistry;
