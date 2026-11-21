# Client API — `uiRegistry`

`uiRegistry` is the client-side UI registry (`UIRegistry` in
`client/scripts/ui.js`). It lets client mods build and manage DOM UI the same
way they register handlers and game state. It is exposed as two globals:
`uiRegistry` and the alias `ui`.

It uses the same auto-namespacing: while a mod's client script is `eval()`ed,
the loader pushes the namespace onto this registry, so any **unqualified** ui
name is prefixed (`"hud"` → `"ui_demo:hud"`). `"core:..."` passes through.

Views, event handlers, and styles are registered by (fully-qualified) name and
looked up / mounted / dispatched later. A view builder can be a function
returning a DOM node or an HTML string.

> **Key runtime rule:** most UI work happens *after* the mod's initial eval(),
> when the namespace stack is empty. For names to resolve at runtime, either use
> the **bound handle** from [`createView`](#createview) or the **bound event**
> from [`bindEvent`](#bindevent) — both capture the namespace when you call them
> and re-enter it on every later call. Don't re-resolve raw names at runtime.

## Namespace management

| Method | Description |
|---|---|
| `pushNamespace(namespace)` | Push a namespace (used by the loader around eval). |
| `popNamespace()` | Pop the top namespace. |
| `currentNamespace()` | Return the top namespace or `null`. |

## Mount root

### `getRoot`

```javascript
getRoot()
```
Return the default mount container. Reuses `#ui-root` if it exists; re-queries
lazily so it works before the DOM is fully parsed.

### `setRoot`

```javascript
setRoot(el)
```
Override the default mount container with a given element (or `null` to reset).

## View registration

### `register_view`

```javascript
register_view(name, buildFn, opts = {})
```

Register a view builder under a (possibly unqualified) name.

```javascript
const fq = uiRegistry.register_view("hud", build_hud, { title: "HUD" });
```

| Param | Type | Description |
|---|---|---|
| `name` | `string` | View name; auto-prefixed with the active namespace. |
| `buildFn` | `(ui, args, container) => Node\|string` | Called lazily on `mount()`. May return a DOM node or an HTML string. |
| `opts` | `object` | Optional extra metadata. |

Returns the fully-qualified name.

### `get_view`

```javascript
get_view(name)
```
Return the `{buildFn, namespace, opts}` record, or `null`.

### `has`

```javascript
has(name)
```
Return `true` if a view is registered under the name.

### `mount`

```javascript
mount(name, target = null, args = null)
```

Create an instance of a registered view and append it to a container. The
builder runs inside the view's namespace.

| Param | Type | Description |
|---|---|---|
| `name` | `string` | View name (resolved through the active namespace). |
| `target` | `HTMLElement\|string\|null` | Container element or CSS selector; defaults to `#ui-root`. |
| `args` | `any` | Value forwarded to the builder. |

Returns the created element, or `null` if the view/container is missing.

### `unmount`

```javascript
unmount(name)
```
Remove every mounted instance of a view.

### `unmountAll`

```javascript
unmountAll()
```
Tear down every view this registry has mounted. There is no automatic client
lifecycle hook, so this is how mods/core clean up.

Also removes every DOM listener registered through
[`register_listener`](#register_listener): a listener usually drives a view, so
leaving it attached after the view is gone means dead handlers firing against
detached elements — and, after a reconnect, duplicated listeners on the same
target. Styles are deliberately left alone; [`clearStyles`](#clearStyles) owns
those.

### `get_el`

```javascript
get_el(name)
```
Return the most recently mounted element for a view.

### `get_instances`

```javascript
get_instances(name)
```
Return all mounted elements for a view.

## Event handlers

### `on`

```javascript
on(event, func, name = null)
```

Register a UI event handler, mirroring `Registry.register_handler`.

```javascript
uiRegistry.on("health_damage", damage_handler);
```

| Param | Type | Description |
|---|---|---|
| `event` | `string` | Event hook name; auto-prefixed. |
| `func` | `Function` | Handler, called as `func(payload, ui, gameState)` on dispatch. |
| `name` | `string, optional` | Handler name; if omitted, a `_ui_<n>` name is generated. |

Returns the (resolved) handler name.

### `get`

```javascript
get(event, name = null)
```
Look up a UI handler record `{func, namespace}`, or a whole event hook object.

### `dispatch`

```javascript
dispatch(event, payload = null, gameState = null)
```

Run every handler under the event, each inside its captured namespace.

```javascript
uiRegistry.dispatch("health_damage", null, gameState);
```

Handlers are called `func(payload, ui, gameState)`. If one throws, it's logged
and re-thrown (with `e.handled = true`), and the namespace is restored.

Handlers may safely call [`unregister_handler`](#unregister_handler) during
dispatch (on themselves or another handler): `dispatch` iterates a snapshot, so
the current dispatch is unaffected and the removal applies from the next one.

### `unregister_handler`

```javascript
unregister_handler(event, name)   // -> true if removed, false if not found
```

Remove a UI event handler registered with [`on`](#on). Mirror of `on()`: same
`(event, name)` pair. Returns `boolean`, so a mistyped name is visible rather
than a silent no-op.

## DOM listeners

A listener handed straight to `target.addEventListener()` is unreachable
afterwards: `removeEventListener` needs the *same* function reference and
capture flag, so a closure created inline can never be uninstalled — not even by
the mod that created it. `register_listener` makes the listener a named,
addressable record instead, so it can be overwritten or removed by name (this is
what lets an addon mod replace another mod's input handling).

### `register_listener`

```javascript
register_listener(target, event, fn, name, opts = {})
```

Attach a DOM listener and remember it under `name`.

```javascript
uiRegistry.register_listener(document, "pointerdown", onPointerDown, "joy_down");
```

| Param | Type | Description |
|---|---|---|
| `target` | `EventTarget` | `window`, `document`, or an element. |
| `event` | `string` | DOM event type (`"pointerdown"`, `"keyup"`, …). |
| `fn` | `Function` | Listener callback. |
| `name` | `string` | **Required** unique name; auto-prefixed with the active namespace. |
| `opts` | `object, optional` | `{ capture }` (default `false`); stored so removal passes a matching flag. |

Returns the fully-qualified listener name.

- **Registering an existing name replaces it.** The previous listener is
  `removeEventListener`'d from its target first, then the new one is attached —
  mirroring `register_handler`. Dropping the record without detaching would leave
  a live, unbindable listener still firing.
- **`name` is mandatory.** Handlers may be auto-named; a listener must not be,
  because an auto-named listener could never be unregistered — which defeats the
  only reason to use this instead of `addEventListener`.
- **Use it for lifetime, not convenience.** A listener owned by a mod that can
  disconnect/reconnect should be registered here so
  [`unmountAll`](#unmountall) / [`clearListeners`](#clearlisteners) can clean it
  up; otherwise a reconnect stacks a duplicate listener on the same target.

> **Runtime note.** Like every other `uiRegistry` name, `name` resolves through
> the active namespace. If you register or remove listeners *after* your mod's
> script has finished evaluating (e.g. on a delayed mount or on disconnect), the
> namespace stack is empty and an unqualified name throws. Capture the
> fully-qualified name while the namespace is still active:
>
> ```javascript
> // during eval:
> const DOWN = uiRegistry.bindName("joy_down");   // -> "mymod:joy_down"
> // later, namespace-free:
> uiRegistry.register_listener(document, "pointerdown", fn, DOWN);
> uiRegistry.unregister_listener(DOWN);
> ```

### `unregister_listener`

```javascript
unregister_listener(name)   // -> true if a listener was attached and removed
```

### `get_listener`

```javascript
get_listener(name)   // -> { target, event, fn, capture, namespace } | null
```

### `list_listeners`

```javascript
list_listeners()   // -> string[] of registered (fully-qualified) names
```

### `clearListeners`

```javascript
clearListeners()
```

Remove every listener registered through `register_listener`. Called
automatically by [`unmountAll`](#unmountall).

## Styles

### `register_style`

```javascript
register_style(cssText, id = null)
```

Inject a `<style>` element and remember its id for cleanup. Calling again with
the same id replaces the content instead of duplicating.

```javascript
const styleId = uiRegistry.register_style(`.hud { position: fixed; top: 12px; }`);
```

| Param | Type | Description |
|---|---|---|
| `cssText` | `string` | CSS rules. |
| `id` | `string, optional` | Explicit id; default is a generated `ui-style-<n>`. |

Returns the style element's id.

### `clearStyles`

```javascript
clearStyles()
```
Remove every style element this registry injected.

## Runtime helpers (the important ones)

These are what make runtime UI work cleanly without a live namespace.

### `createView`

```javascript
createView(name, buildFn, opts = {})
```

Register a view **and** get a bound handle. This is the recommended way to build
UI. You call it once at load time (while your namespace is active); the handle
captures that namespace, so every method below re-enters it for you.

```javascript
const hud = uiRegistry.createView("hud", build_hud);
hud.mount();   // safe here AND safe later at runtime
```

Returns an object with these methods:

| Method | Description |
|---|---|
| `handle.el` | The most recently mounted element (initially `null`, set after `mount()`). |
| `handle.name` | The fully-qualified view name. |
| `handle.mount(target, args)` | Mount an instance into `#ui-root` or a custom target. |
| `handle.update(fn)` | Run `fn(handle.el, uiRegistry)` inside this view's namespace. |
| `handle.set(selector, value)` | Set `textContent` of the first element matching a CSS selector. |
| `handle.on(selector, event, fn)` | Attach a DOM event listener to an element inside the view. |
| `handle.unmount()` | Remove every mounted instance of this view. |

### `bindEvent`

```javascript
bindEvent(event)
```

Capture an event name + this namespace and return a safe dispatcher closure.

```javascript
hud.on("[data-hit]", "click", uiRegistry.bindEvent("health_damage"));
```

The returned closure, when called (from a click, timer, etc.), dispatches the
event with this mod's namespace re-entered. The handlers for the event are
registered separately with `on()`; `bindEvent` only captures the event +
namespace and produces the safe dispatcher.

### `bindName`

```javascript
bindName(name)
```

Resolve a name now and return its fully-qualified form, so a caller can use it
at runtime without relying on a live namespace on the stack.

## Example (from `mods/ui_demo/client.js`)

```javascript
// At load time (namespace active):
const hud = uiRegistry.createView("hud", build_hud);
hud.mount();

uiRegistry.on("health_damage", damage_handler);
uiRegistry.on("hud_toggle", toggle_handler);

hud.on("[data-hit]", "click", uiRegistry.bindEvent("health_damage"));
hud.on("[data-toggle]", "click", uiRegistry.bindEvent("hud_toggle"));

// At runtime (namespace stack is empty, but the handle re-enters it):
wsRegistry.register_handler("core:tick", function (gameState) {
    const speed = gameState.get(["core:playerData", "speed"], 8);
    hud.set("[data-mod]", `ui_demo (speed ${speed})`);
}, "tick_ui");

// Cleanup on client disconnect:
wsRegistry.register_handler("core:on_disconnect", function () {
    hud.unmount();
    uiRegistry.clearStyles();
}, "disconnect_cleanup");
```

## Globals

- `uiRegistry` — the `UIRegistry` instance.
- `ui` — alias for the same instance, handy in templates/builders.

## Notes

- The default mount container is `#ui-root` (present in `client/frontend.html`).
- There is **no automatic client-side lifecycle hook** (the server has
  `core:on_player_disconnect`, but the client has no parallel). Use
  `core:on_disconnect` (client hook) + `unmountAll()`/`clearStyles()` to clean
  up, as `ui_demo` does.

## Source

`client/scripts/ui.js`
