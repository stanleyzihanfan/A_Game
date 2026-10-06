# `manifest.json`

Every mod is a folder under `mods/` containing a `manifest.json`. This is the
single file that declares the mod's identity and which of its files the loader
should run. It is read by `server/mod_loader.py`.

## Schema

```json
{
    "modID": "my_mod",
    "namespace": "my_mod",
    "name": "My Mod",
    "version": "0.1.0",
    "description": "What this mod does",
    "author": "Your Name",
    "backend_py": "main.py",
    "client_js": "client.js",
    "enabled": true,
    "dependencies": []
}
```

## Fields

### `modID` — required
The unique identifier of the mod. It is also the folder name under `mods/`.
Used as the module name when the backend is dynamically imported.

### `namespace` — optional, defaults to `modID`
The auto-namespacing prefix for everything this mod registers (ops, handlers,
state keys, UI names). See [Concepts](concepts.md#3-namespacing).

Validation (in `mod_loader._get_namespace`):

- Cannot be `"core"` — that is reserved for the game engine.
- Can only contain letters, digits, `_`, and `-`. No `:`.
- If it is missing, the loader falls back to `modID`.

### `name` — recommended
Human-readable mod name, printed during load.

### `version` — recommended
String version, printed during load.

### `description` — optional
What the mod does. Shown in logs and useful for the mod list.

### `author` — optional
The mod's author.

### `backend_py` — optional
Path (relative to the mod folder) to the Python file that exposes
`def register(registry)`. Default is `"main.py"` if you want to rely on the
convention; the loader requires the field to be non-empty to load a backend.

- **Absent or empty string** → the mod is **client-side only**; no backend is
  imported and no `register()` is expected. (No warning is emitted.)
- If the field is set but the file is missing, the loader prints a warning.

### `client_js` — optional
Path (relative to the mod folder) to the JavaScript file streamed to the client.
It is `eval()`ed during the handshake.

- **Absent or empty string** → the mod is **server-side only**; nothing is
  streamed and no warning is emitted.

### `enabled` — optional, defaults to `true`
When `false`, the mod is **not loaded at all**: its backend is not imported, no
handlers are registered, and its `client.js` is not streamed. Its files and code
are left intact.

### `dependencies` — optional, defaults to `[]`
Reserved for future topological sorting. **Currently ignored**: load order is
alphabetical by `modID` (see `_load_order` in `mod_loader.py`).

## Full examples

### Server-side only
```json
{
    "modID": "connect_guard",
    "namespace": "connect_guard",
    "name": "Connection Guard",
    "version": "0.1.0",
    "description": "Validates player name/password on connect",
    "author": "Eyeseminal",
    "backend_py": "main.py",
    "client_js": "",
    "dependencies": []
}
```

### Client-side only
```json
{
    "modID": "ui_demo",
    "namespace": "ui_demo",
    "name": "UI Demo",
    "version": "0.1.0",
    "description": "Demonstrates the client-side UI registry",
    "author": "Eyeseminal",
    "backend_py": "",
    "client_js": "client.js",
    "dependencies": []
}
```

A mod with both halves sets both `backend_py` and `client_js` (see
`mods/player_position/manifest.json`).

## The `register()` contract

If you set `backend_py`, that file must expose a top-level function:

```python
def register(registry):
    # subscribe to hooks
    registry.register_handler("core:tick", my_handler, "my-handler")
```

- It is called with a single argument: the `Registry` instance.
- It is called **inside the mod's namespace** (the loader holds the namespace
  active around the call), so unqualified op/handler names are auto-prefixed.
- If a backend mod does not expose `register()`, the loader prints a warning
  and does nothing for it.

## Load order & failure

- Mods are loaded in **alphabetical order by `modID`**, not by dependency.
- A mod whose `manifest.json` is missing is skipped with a warning.
- A mod whose `namespace` is invalid or `core` is skipped with a warning.
- A mod with `enabled: false` is skipped.
- If a mod's `register()` raises, the exception propagates (the server treats a
  broken mod as fatal rather than swallowing it), but the namespace stack is
  always restored in a `finally` block.
