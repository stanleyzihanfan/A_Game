# Server API — `Registry`

The `Registry` (in `server/ws_registry.py`) is the server-side handler registry.
A server mod receives it as the single argument to `register(registry)` and uses
it to subscribe to event hooks and to fire its own. It manages the
auto-namespacing stack under the hood; you rarely touch that directly.

Type names follow the project's own docstrings: the object is a `Registry`, a
`register_handler`/`dispatch`-style API, and handler functions are called with
`(gameState, registry)`.

## Instance you get

Inside `register(registry)`, `registry` is the app's single shared `Registry`
instance (created in `server/core.py` as `registry`).

## `register_handler`

```python
register_handler(op, func=None, name=None)
```

Register a handler on an event hook. This is the main thing a mod does at load
time.

```python
registry.register_handler("core:tick", my_tick_handler, "my-tick-handler")
```

**Parameters**

| Param | Type | Description |
|---|---|---|
| `op` | `str` | Event hook name. Unqualified names auto-prefix with the mod's namespace; `"core:..."` passes through. |
| `func` | `callable` | The handler. Called as `func(gameState, region_registry)` on dispatch. If `None`, only the hook is created (no handler is added). |
| `name` | `str, optional` | Handler name. If omitted, a `_lambda_<id>` name is generated to avoid collisions. |

**Behavior**

- Unqualified `op` / `name` are resolved against the current namespace.
- If the hook does not exist yet, it is created.
- If `func` is `None`, the hook is created and the function returns — use this
  to declare an op that other code dispatches into, without adding a handler.
- If a handler with the same name already exists under the hook, it is
  **overwritten** (with a warning).
- The handler **captures the namespace active at registration**, so `dispatch()`
  can re-enter it later.

**Example** — declaring a hook, then adding a handler:

```python
def register(registry):
    # Just declare the hook (no handler):
    registry.register_handler("core:my_own_hook", None)

    # Add a handler to an existing hook (core hook, passes through):
    registry.register_handler("core:tick", on_tick, "on_tick")

    # Unqualified name auto-prefixes to "<namespace>:my_hook":
    registry.register_handler("my_hook", on_my_hook, "on_my_hook")
```

## `dispatch`

```python
dispatch(op, gameState)
```

Run every handler registered under `op`, in registration order, each inside the
namespace it was registered under.

```python
registry.dispatch("core:my_own_hook", game_state)
```

**Parameters**

| Param | Type | Description |
|---|---|---|
| `op` | `str` | Hook to dispatch. **Not auto-namespaced** — passed as-is. |
| `gameState` | `GameState` | Passed to every handler. Also gets its namespace pushed/popped alongside. |

**Behavior**

- Calls each handler as `func(gameState, registry)`.
- Each handler runs inside its captured namespace, so its own unqualified names
  resolve correctly.
- If a handler raises, the error is printed with a traceback and re-raised (with
  a `"Handled"` note). The namespace is restored in a `finally` block.
- If no handlers are registered, it is a no-op (already handled by `get_handler`
  returning `None`).

## `get_handler`

```python
get_handler(op, name=None)
```

Look up a handler record or a whole hook. Returns `None` if not found.

```python
record = registry.get_handler("core:tick", "my-tick-handler")            # single record
hook   = registry.get_handler("core:tick")                               # whole dict {name: record}
```

- With `name`: returns the record `{"func": callable, "namespace": str|None}`.
  Use `record["func"]` to call it.
- Without `name`: returns the full hook dict, `{handlerName: record}`.
- Both `op` and `name` are resolved against the active namespace (so in a mod
  handler you can use unqualified names).

## `current_namespace()`

Return the active namespace (`str`) or `None` if not inside mod loading.

```python
ns = registry.current_namespace()
```

Useful for reading data the client sent under this mod's namespaced key (see
the `player_position` mod, which builds `f"{ns}:movement_handler"`).

## Namespace helpers

These are the stack primitives the loader uses. You normally do not call them,
but they are public:

| Method | Description |
|---|---|
| `push_namespace(namespace)` | Push a namespace onto the stack. |
| `pop_namespace()` | Pop the top namespace. |
| `current_namespace()` | Return the top namespace or `None`. |

## Notes

- The registry is **shared** across all mods and the core. Handlers from
  different mods live under the same hook key but are namespaced apart.
- `"core:tick"` is pre-seeded in the handler dict on the Python side
  (`self._handlers = {"core:tick": {}}`) and is the hook the server dispatches
  for per-tick work.
- Cross-namespace references are allowed; the registry does not police who may
  listen to whose ops.

## Source

`server/ws_registry.py`
