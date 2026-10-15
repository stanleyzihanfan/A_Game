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
    "dependencies": [],
    "incompatibilities": []
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
A list of dependencies this mod needs loaded first. The loader **topologically
sorts** by these so that every dependency loads **before** the mod that depends
on it. This lets a mod rely on the handlers / state its dependencies registered
during their own `register()`.

Each entry is either a **string** or a **dict**:

```json
{
    "modID": "my_mod",
    "dependencies": [
        "scene_setup",                                  // plain: any version
        "player_position>=0.2.0",                       // string + version spec
        {"modID": "ui_demo", "version": ">=0.1.0,<1.0"} // dict with version spec
    ]
}
```

The identifier is a **`modID`**, not a namespace. The optional **version spec**
pins which version of that dependency this mod needs. Supported operators:
`==`, `!=`, `>=`, `<=`, `>`, `<`, `~=` (compatible release), plus a bare version
(treated as `==`) and comma-separated ANDs (`">=0.2.0,<1.0"`). A missing or
blank spec matches any version.

Rules (see `_load_order` in `mod_loader.py`):

- A dependency that **won't load** — missing, disabled (`enabled: false`), itself
  skipped, or whose **version does not satisfy the spec** — causes the dependent
  mod to be **skipped** (with a warning). This cascades: mods that depend on the
  skipped mod are skipped too.
- A **dependency cycle** (e.g. `a` → `b` → `a`) is detected and broken
  deterministically at the alphabetically-first mod in the cycle, with a warning,
  so the rest of the load proceeds in dependency order. Each **independent**
  cycle is reported separately (a mod's cycle group is found via strongly
  connected components), so with e.g. `a` ↔ `b` and `c` ↔ `d` the loader warns
  about `['a', 'b']` and `['c', 'd']` as two distinct cycles rather than lumping
  them together.
- A mod depending on **itself** is ignored with a warning.
- A non-list, non-string, or non-dict `dependencies` entry is ignored with a
  warning.
- Mods with **no dependencies** continue to load in alphabetical order, so
  existing mods keep their previous behavior.

### `incompatibilities` — optional, defaults to `[]`
A list of mods this mod **cannot work alongside**. If a loaded mod matches an
entry, the two are incompatible and the server **refuses to start**, printing
**all** detected conflicts at once so they can be fixed in one go. This is fatal
— the loader stops rather than running a broken combination.

Each entry uses the same string-or-dict form as `dependencies`, and the optional
version spec narrows *which* versions of the conflicting mod actually clash:

```json
{
    "modID": "my_mod",
    "incompatibilities": [
        "old_demo",                 // incompatible with any version of old_demo
        "another_mod>=1.0.0",       // incompatible with another_mod v1.0.0+
        {"modID": "legacy", "version": "<0.5"}  // dict form
    ]
}
```

Semantics:

- The check only considers mods that will **actually load**. A conflicting mod
  that is missing or disabled is ignored — there is nothing to clash with.
- An entry with **no version** matches any version of the other mod.
- An entry **with a version** only matches if the other mod's version satisfies
  it (i.e. the pair is only incompatible for those versions).
- Since this is fatal, the standard `register()` failure path (which is also
  fatal) is matched: a broken mod mix stops the server rather than degrading.

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

- Mods are loaded in **topological order by `dependencies`**; mods with no
  dependencies load alphabetically by `modID`. See
  [`dependencies`](#dependencies-optional-defaults-to).
- A mod whose `manifest.json` is missing is skipped with a warning.
- A mod whose `namespace` is invalid or `core` is skipped with a warning.
- A mod with `enabled: false` is skipped.
- A mod that depends on an unavailable mod — missing, disabled, itself skipped,
  or whose **declared version spec isn't satisfied** — is skipped with a warning,
  and this cascades.
- A **detected incompatibility** among the mods that will load is **fatal**: the
  loader raises, listing every conflict, and the server refuses to start. See
  [`incompatibilities`](#incompatibilities-optional-defaults-to).
- If a mod's `register()` raises, the exception propagates (the server treats a
  broken mod as fatal rather than swallowing it), but the namespace stack is
  always restored in a `finally` block.
