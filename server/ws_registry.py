import traceback
from server.game_state import GameState

# Central WebSocket op handler registry
# Replaces the wsDispatch dict in the original backend.py
# Mods call register_handler() to add their own ops
#
# Namespacing:
# The registry tracks an "active namespace" (set by the mod loader while a
# mod's register() runs). Any unqualified op or handler name (no ":") is
# automatically prefixed with it: "syncBlocks" -> "testmod:syncBlocks".
# Strings that already contain ":" (e.g. every "core:something") pass
# through untouched, so core hooks stay hard-coded.
# While no mod is loading (namespace None), unqualified strings are an error:
# outside of mod loading, everything must be explicitly namespaced.
class Registry:
    def __init__(self):
        self._handlers = {"core:tick":{}}
        # Stack of active namespaces; top frames the mod currently loading.
        # None (or empty) means "not loading a mod" — no implicit namespace.
        self._namespace_stack = []

    # -- Namespace management ---------------------------------------------------
    def push_namespace(self, namespace):
        """Enter a mod's namespace. Call before loading a mod, pop after.

        :param namespace: Namespace string from the mod's manifest.json
        """
        self._namespace_stack.append(namespace)

    def pop_namespace(self):
        """Leave the most recently pushed namespace."""
        if self._namespace_stack:
            self._namespace_stack.pop()

    def current_namespace(self):
        """Return the active namespace, or None if not inside mod loading."""
        return self._namespace_stack[-1] if self._namespace_stack else None

    def _resolve(self, name):
        """Prefix an unqualified name with the active namespace.

        Strings that already contain ":" (e.g. "core:tick_hook") are returned
        unchanged. Qualified strings with a foreign namespace are also kept
        as-is — cross-namespace references are allowed, the registry does not
        police who may listen to whose ops.

        :param name: Op or handler name to resolve
        :return: Fully-qualified name
        :raises RuntimeError: If name is unqualified and no namespace is active
        """
        if name is None:
            return name
        if ":" in name:
            return name
        namespace = self.current_namespace()
        if namespace is None:
            raise RuntimeError(
                f"Cannot use unqualified name '{name}' outside of mod loading — "
                f"ops and handler names must be namespaced (e.g. 'mymod:{name}')"
            )
        return f"{namespace}:{name}"

    def register_handler(self, op: str, func=None, name:str = None):
        """
        Register a handler

        Unqualified op/handler names are automatically prefixed with the
        namespace of the mod being loaded (see manifest.json "namespace").
        The handler remembers the namespace active at registration, and
        dispatch() re-enters it while the handler runs — so the handler's
        own unqualified names/keys keep resolving to its mod's namespace
        even when dispatched long after loading.

        :param op: Name of event hook
        :param funct: Function object of handler
        :param name: Name of handler function
        """
        handlerName=name
        # Capture the namespace active at registration (None for core code)
        handlerNamespace = self.current_namespace()
        op = self._resolve(op)
        if name is not None:
            name = self._resolve(name)
            handlerName=name
        #Create new event hook if not created
        if not op in self._handlers:
            self._handlers[op]={}
            print(f"  Event Hook {op} created.")
        #Exit early if no function is provided(only registers event hook)
        if func is None:
            return
        #If name is not provided, replace with _lambda+unique function ID to prevent collision
        if handlerName==None:
            handlerName=f"_lambda_{id(func)}"
        #Warn if another handler with same name already exists
        if handlerName in self._handlers[op]:
            print(f"\033[33m    [WARN] Handler {handlerName} already registered under {op}, overwriting!\033[0m")
        #Register function in _handlers
        self._handlers[op][handlerName]={"func":func,"namespace":handlerNamespace}
        print(f"    New handler {handlerName} registered under {op}.")

    def get_handler(self, op:str, name:str = None):
        """
        Get a handler

        :param op: Event hook to look under
        :param name: Optional, name of handler to get
        :return: If name is provided, returns the handler record
        {"func", "namespace"} (use ["func"] for the callable).
        If name is not provided/None, returns full event hook of
        handler+name as a dictionary.
        Returns None if not found.
        """
        op = self._resolve(op)
        if name is not None:
            name = self._resolve(name)
        #Return handler if name is provided
        if name and op in self._handlers:
            return self._handlers[op].get(name)
        #Return full dict under event hook(name not provided)
        return self._handlers.get(op)

    #Dispatch a hook/handler
    def dispatch(self, op: str, gameState:GameState):
        """
        Dispatch a hook/handler

        Dispatch intentionally does NOT auto-namespace the op itself: op is
        used as given. But each handler is invoked inside the namespace it
        was registered under (None for core code), so its own unqualified
        names/keys resolve to its mod's namespace at runtime — the "assume
        the namespace it gets called in" behavior.

        :param op: Event hook to dispatch
        """
        handlers=self.get_handler(op)
        if handlers:
            for handlerName,record in handlers.items():
                func=record["func"]
                namespace=record["namespace"]
                if namespace is not None:
                    self.push_namespace(namespace)
                    if gameState is not None and hasattr(gameState,"push_namespace"):
                        gameState.push_namespace(namespace)
                try:
                    func(gameState,self)
                except Exception as e:
                    print(f"\x1b[31mHandler '{handlerName}' under '{op}' failed:\033[0m")
                    traceback.print_exc()
                    e.add_note("Handled")
                    raise
                finally:
                    if namespace is not None:
                        self.pop_namespace()
                        if gameState is not None and hasattr(gameState,"pop_namespace"):
                            gameState.pop_namespace()