"""
Central game state storage and accessing handler.

GameState provides a thread-safe nested key-value store used by the server
to hold world data, player data, and temporary runtime values.

Namespacing:
The FIRST element of a key decides its namespace, e.g. ["players", ...] is
core game data. Mods get automatic namespacing through the same active-
namespace mechanism as the Registry: while a mod's code runs (during mod
loading), any UNQUALIFIED key — one whose first element contains no ":" —
is prefixed with that mod's manifest namespace. Keys whose first element
already contains ":" (e.g. ["core:client_receive_buffer", ...]) pass
through untouched, so core keys stay hard-coded.
"""
import threading, copy
#Central game state storage and accessing handler
class GameState:
    def __init__(self):
        self._state={}
        self._lock=threading.RLock()
        # Stack of active mod namespaces (mirrors Registry._namespace_stack).
        # Empty means "not inside mod code" — unqualified keys then reference
        # core game data as before, preserving existing behavior.
        self._namespace_stack = []

    # -- Namespace management ---------------------------------------------------
    def push_namespace(self, namespace):
        """Enter a mod's namespace. Mod loader calls this around register().

        :param namespace: Namespace string from the mod's manifest.json
        """
        self._namespace_stack.append(namespace)

    def pop_namespace(self):
        """Leave the most recently pushed namespace."""
        if self._namespace_stack:
            self._namespace_stack.pop()

    def current_namespace(self):
        """Return the active namespace, or None if not inside mod code."""
        return self._namespace_stack[-1] if self._namespace_stack else None

    def _resolve(self, key: list) -> list:
        """Prefix an unqualified key's first element with the active namespace.

        A key is unqualified if its first element contains no ":". Qualified
        keys (e.g. ["core:global_broadcast"]) are returned unchanged — this is
        what keeps all "core:something" usages working as before.

        :param key: Key list to resolve
        :return: New key list with first element namespaced if unqualified
        """
        if not key:
            return key
        if ":" in str(key[0]):
            return key
        namespace = self.current_namespace()
        if namespace is None:
            return key
        return [f"{namespace}:{key[0]}"] + list(key[1:])

    def set(self,key:list,value,override=False):
        """Sets a key-value pair to game state

        Unqualified keys are auto-namespaced with the active mod namespace
        (see module docstring). Keys are lists, e.g. ["players", "Alice", "pos"].

        :param key: Key to add
        :param value: Value to add
        :param override: Whether to override any conflicting leaves
        """
        with self._lock:
            key = self._resolve(key)
            last = self._state
            for k in key[:-1]:
                if k not in last or not isinstance(last[k], dict):
                    if k in last and not override:
                        raise KeyError(f'Key {key} does not exist in game state')
                    last[k] = {}
                last = last[k]
            last[key[-1]] = value

    def get(self,key:list,default=None, deepcopy=True):
        """Gets value for key

        Unqualified keys are auto-namespaced with the active mod namespace.
        WARNING: When using deepcopy=False, make sure it is used with thread lock

        :param key: Key to get value for
        :param default: Default value
        :param deepcopy: Whether to return a deep copy of value
        :return: Returns value if key exists, else returns default
        """
        with self._lock:
            key = self._resolve(key)
            last=self._state
            for k in key:
                if not isinstance(last,dict) or k not in last:
                    return default
                last=last[k]
            if deepcopy:
                return copy.deepcopy(last)
            else:
                return last

    def exists(self,key:list):
        """Get if a key exists

        Unqualified keys are auto-namespaced with the active mod namespace.

        :param key: Key to check
        :return: Boolean if key exists or not
        """
        with self._lock:
            key = self._resolve(key)
            last = self._state
            for k in key:
                if not isinstance(last,dict) or k not in last:
                    return False
                last = last[k]
            return True
    
    def initialize(self,key:list,value):
        """Helper function to initialize a value if it does not exist, else do nothing

        :param key: key to initialize
        :param value: Value to initialize to
        """
        with self._lock:
            if not self.exists(key):
                self.set(key,value,True)

    # -- Send/receive buffer helpers --------------------------------------------
    # These wrap the core sync buffers so mods never have to touch raw
    # "core:*" keys themselves. add_to_broadcast/add_to_client_sync
    # auto-namespace their unqualified key arguments with the active mod
    # namespace (manifest "namespace").
    def _resolve_message_key(self, key: str) -> str:
        """Resolve a single message key (not a key list) to its namespaced form.

        :param key: Message key, e.g. "pos"
        :return: Namespaced key, e.g. "player_position:pos"
        :raises RuntimeError: If key is unqualified and no namespace is active
        """
        if not isinstance(key, str):
            raise TypeError(f"Message key must be a string, got {type(key).__name__}")
        if ":" in key:
            return key
        namespace = self.current_namespace()
        if namespace is None:
            raise RuntimeError(
                f"Cannot use unqualified message key '{key}' outside of mod code — "
                f"message keys must be namespaced (e.g. 'mymod:{key}')"
            )
        return f"{namespace}:{key}"

    def add_to_broadcast(self, key: str, value):
        """Add a key-value pair to the global broadcast buffer.

        The buffer is flushed to every connected client each tick. The key is
        namespaced automatically ("mydata" -> "mymod:mydata"), so a mod can
        never collide with another mod's broadcast keys.

        :param key: Unqualified key to broadcast under
        :param value: Value to send
        """
        with self._lock:
            key = self._resolve_message_key(key)
            buffer = self.get(["core:global_broadcast"])
            if not isinstance(buffer, list):
                buffer = []
            buffer.append({key: value})
            self.set(["core:global_broadcast"], buffer)

    def add_to_client_sync(self, key: str, value):
        """Add a key-value pair to the current per-client sync payload.

        Must be called from a "core:calculate_client_display" handler — the
        payload only exists while the server computes one client's display
        data. The key is namespaced automatically.

        :param key: Unqualified key to sync under
        :param value: Value to send
        """
        with self._lock:
            key = self._resolve_message_key(key)
            payload = self.get(["core:per_client_sync", "data"])
            if not isinstance(payload, dict):
                payload = {}
            payload[key] = value
            self.set(["core:per_client_sync", "data"], payload)

    def get_client_messages(self, playerName: str = None):
        """Collect the messages a client sent this tick.

        Returns the list of {"playerName", "data"} dicts the given player
        (or every player, if no name is given) pushed into the receive
        buffer this tick.

        :param playerName: Optional player to filter messages for
        :return: List of {"playerName", "data"} dicts (deep copies)
        """
        with self._lock:
            buffer = self.get(["core:client_receive_buffer"], default=[])
            if playerName is None:
                return buffer
            return [entry for entry in buffer if entry.get("playerName") == playerName]