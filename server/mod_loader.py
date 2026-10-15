"""
Mod loader module.

Scans the /mods directory, reads each manifest.json, and loads each mod's
backend_py in order, calling register(registry) on each one.

Namespacing:
Each manifest.json declares a "namespace" string (defaults to modID when
absent). While a mod loads, the loader pushes that namespace onto the
Registry and GameState namespace stacks, so every unqualified op, handler
name, and game-state key the mod uses is automatically prefixed with it —
the mod never writes "namespace:something" itself. All "core:something"
strings pass through untouched (they are hard-coded by design).
"""
import os, json, importlib.util, re

class ModIncompatibilityError(Exception):
    """Raised when two mods that will be loaded declare an incompatibility.

    Carries the list of detected conflicts. The server treats a broken mod mix
    as fatal: it stops loading and refuses to start rather than running with
    mods that declared themselves incompatible.
    """

# -- Mod loader ----------------------------------------------------------------
# Scans the /mods directory, reads each manifest.json, and loads each mod's
# backend_py in order, calling register(registry) on each one.
# Note: below, MODS_DIR is the absolute path to the /mods folder at project root.

MODS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mods")

# -- Namespace helpers -----------------------------------------------------------
# Determines a mod's namespace from its manifest, with fallback + validation.
def _get_namespace(manifest):
    """Return the mod's namespace with fallback and validation.

    Namespace defaults to modID when the manifest has no "namespace" field.
    "core" is reserved for the game engine itself and rejected.

    :param manifest: The mod's manifest dict
    :return: Namespace string
    """
    namespace = manifest.get("namespace") or manifest["modID"]
    if namespace == "core":
        raise ValueError(f"Mod '{manifest['modID']}' declares namespace 'core', which is reserved for the game engine")
    if ":" in namespace or not namespace.replace("_","").replace("-","").isalnum():
        raise ValueError(f"Mod '{manifest['modID']}' declares invalid namespace '{namespace}' (letters, digits, _ and - only, no ':')")
    return namespace


# -- Version handling ------------------------------------------------------------
# Self-contained PEP-440-lite version parsing and specifier matching, so the mod
# loader can satisfy "dependencies": ["mod>=1.2"] and incompatibility version
# gates without pulling in the third-party `packaging` library (which is not
# installed in the server runtime).


def _version_tuple(v):
    """Parse a version string into a sortable, comparable tuple.

    Supports dotted numeric releases and an optional pre-release suffix (e.g.
    '1.2.3-beta.1'). Build metadata after '+' is ignored. Missing components are
    treated as 0, so '1.2' == '1.2.0'. A pre-release sorts BEFORE its final
    release, so 1.0.0-beta < 1.0.0.

    :param v: version string
    :return: (release_tuple_3, pre_release_flag, pre_suffix)
    :raises ValueError: If the version cannot be parsed
    """
    v = str(v).strip().split("+", 1)[0]
    m = re.match(r"^(\d+(?:\.\d+)*)(?:[-.]([A-Za-z][A-Za-z0-9]*))?$", v)
    if not m:
        raise ValueError(f"Unrecognized version string: {v!r}")
    release = tuple(int(x) for x in m.group(1).split("."))
    while len(release) < 3:
        release += (0,)
    pre = m.group(2)
    return (release, 1 if pre is None else 0, pre or "")


def _release_with_count(v):
    """Return (release_tuple_3, segment_count) for a version string.

    segment_count is how many dotted numeric segments the release actually had
    before padding (needed for the '~=' compatible-release upper bound).

    :raises ValueError: If the version cannot be parsed
    """
    v = str(v).strip().split("+", 1)[0]
    m = re.match(r"^(\d+(?:\.\d+)*)", v)
    if not m:
        raise ValueError(f"Unrecognized version string: {v!r}")
    nums = [int(x) for x in m.group(1).split(".")]
    count = len(nums)
    while len(nums) < 3:
        nums.append(0)
    return (tuple(nums), count)


def _compatible_release(base_spec, version):
    """Check PEP-440 '~=' (compatible release) semantics.

    ~=X.Y.Z means >=X.Y.Z and <X.(Y+1).0 ; ~=X.Y means >=X.Y and <(X+1).0 ;
    ~=X means >=X and <(X+1).0.
    """
    base, count = _release_with_count(base_spec)
    target, _ = _release_with_count(version)
    if target < base:
        return False
    if count == 1:
        upper = (base[0] + 1, 0, 0)
    else:
        upper_list = list(base[:count - 1])
        upper_list[-1] += 1
        upper = (tuple(upper_list) + (0, 0, 0))[:3]
    return target < upper


def _matches_specifier(spec, version):
    """Return True if `version` satisfies the single specifier clause `spec`."""
    spec = spec.strip()
    if not spec or spec == "*":
        return True
    m = re.match(r"^(==|!=|>=|<=|>|<|~=)?\s*(.+)$", spec)
    if not m:
        raise ValueError(f"Unrecognized version specifier: {spec!r}")
    op = m.group(1) or "=="
    base = m.group(2).strip()
    try:
        v = _version_tuple(version)
        b = _version_tuple(base)
    except ValueError:
        return False
    if op == "==":
        return v == b
    if op == "!=":
        return v != b
    if op == ">":
        return v > b
    if op == "<":
        return v < b
    if op == ">=":
        return v >= b
    if op == "<=":
        return v <= b
    if op == "~=":
        try:
            return _compatible_release(base, version)
        except ValueError:
            return False
    return False


def _version_matches(spec, version):
    """Return True if `version` satisfies a version spec.

    Spec may be a single operator clause ('>=0.2.0'), a bare version ('0.2.0',
    treated as ==), or a comma-separated AND of clauses ('>=0.2.0,<1.0'). A
    blank/None spec matches anything.

    :param spec: version spec string or None
    :param version: installed version string
    :return: bool
    """
    if spec is None:
        return True
    spec = str(spec).strip()
    if not spec or spec == "*":
        return True
    for clause in spec.split(","):
        clause = clause.strip()
        if clause and not _matches_specifier(clause, version):
            return False
    return True


# -- Dependency / incompatibility entry parsing ---------------------------------
# A dependency or incompatibility entry may be either:
#   - a plain string: 'player_position' (no version), or 'scene_setup>=0.2.0'
#     (operator-prefixed version spec)
#   - a dict: {'modID': 'scene_setup', 'version': '>=0.2.0'}


def _parse_dependency_entry(entry, modID, field):
    """Parse a single dependency/incompatibility entry into (other_modID, spec).

    :param entry: The entry to parse (string or dict)
    :param modID: The mod declaring it (for warning messages)
    :param field: Field name ('dependencies' or 'incompatibilities')
    :return: (other_modID, spec_or_None)
    :raises ValueError: If the entry is malformed
    """
    spec = None
    if isinstance(entry, str):
        m = re.match(r"^\s*([A-Za-z0-9_-]+)\s*(.*)$", entry)
        if not m:
            raise ValueError(f"mod '{modID}' {field} entry {entry!r} is not a valid mod specifier")
        other = m.group(1)
        spec = m.group(2).strip() or None
    elif isinstance(entry, dict):
        other = entry.get("modID")
        if not isinstance(other, str) or not other:
            raise ValueError(f"mod '{modID}' {field} entry {entry!r} is missing a valid 'modID'")
        version = entry.get("version")
        if version is not None:
            spec = str(version).strip() or None
    else:
        raise ValueError(f"mod '{modID}' has a {field} entry {entry!r} that is not a string or dict")
    # A spec must start with a version operator (= <>!~) or a digit (bare version).
    if spec and not re.match(r"^[=<>!~0-9]", spec):
        raise ValueError(f"mod '{modID}' {field} entry {entry!r} has an invalid version spec {spec!r}")
    return other, spec


def _parse_dependency_list(raw, modID, field, drop_self=True):
    """Parse a mod's dependencies or incompatibilities into {other_modID: spec}.

    Warns (and skips) malformed entries. For 'dependencies', a mod depending on
    itself is dropped with a warning; for 'incompatibilities', a mod listing
    itself as incompatible is likewise dropped.

    :param raw: The raw field value (list, or anything else)
    :param modID: The mod declaring the field
    :param field: Field name for messages
    :param drop_self: Whether to drop a self-reference
    :return: dict {other_modID: spec_or_None}
    """
    if raw is None:
        return {}
    if not isinstance(raw, list):
        print(f"\x1b[33m  Mod '{modID}' has a non-list '{field}' field, treating it as none\033[0m")
        return {}
    result = {}
    for entry in raw:
        try:
            other, spec = _parse_dependency_entry(entry, modID, field)
        except ValueError as e:
            print(f"\x1b[33m  {e}, ignoring it\033[0m")
            continue
        if other == modID:
            if drop_self:
                print(f"\x1b[33m  Mod '{modID}' lists itself in '{field}', ignoring that entry\033[0m")
                continue
        result[other] = spec
    return result


def _cycle_groups(remaining, deps):
    """Find the distinct dependency-cycle groups among `remaining`.

    A "cycle group" is a strongly connected component (SCC) of the dependency
    subgraph induced by `remaining` that contains more than one mod. Because
    self-dependencies are discarded up front, an SCC of size 1 is never a real
    cycle, so only multi-mod SCCs are returned. Each group is returned sorted.

    This is what lets the loader report each independent cycle separately
    (e.g. a<->b and c<->d are two distinct groups), instead of lumping every
    stuck mod into one message.

    :param remaining: set of modIDs still not ordered
    :param deps: dict of modID -> set of modIDs it depends on (loadable only)
    :return: list of sorted lists, each a distinct cycle group
    """
    # Tarjan's strongly connected components, on the subgraph induced by `remaining`.
    index = {}
    lowlink = {}
    on_stack = set()
    stack = []
    counter = [0]
    groups = []

    def strongconnect(v):
        index[v] = lowlink[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in deps[v]:
            if w not in remaining:
                continue
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            # Only multi-mod SCCs are genuine cycles (self-loops were removed).
            if len(comp) > 1:
                groups.append(sorted(comp))

    for v in sorted(remaining):
        if v not in index:
            strongconnect(v)
    return groups

def _load_order(manifests):
    """
    Return mod folders in load order, topologically sorted by dependencies.

    A mod's manifest may declare a "dependencies" list of modID strings. Every
    dependency is guaranteed to load BEFORE the mod that depends on it, so a mod
    can rely on the handlers / state its dependencies registered during their own
    register(). Mods with no dependencies keep their old alphabetical order, so
    the result stays deterministic and unchanged for existing mods.

    Failure handling (consistent with the loader's warn-and-skip philosophy; a
    config problem never crashes the whole load):
      - A mod that depends on a modID that will NOT be loaded — because it is
        missing, disabled (enabled:false), or itself skipped — is skipped with a
        warning. This cascades: mods that depend on a skipped mod are skipped
        too.
      - A dependency whose declared version spec is NOT satisfied by the
        dependency's manifest version is skipped with a warning (and cascades).
      - Dependency cycles are detected and broken deterministically at the
        alphabetically-first mod of each cycle, with a warning. Each distinct
        (strongly connected) cycle group is reported separately, so multiple
        independent cycles each get their own warning instead of one merged
        message.
      - A self-dependency is ignored with a warning.
      - A non-list or non-string "dependencies" value is ignored with a warning.

    :param manifests: dict of modID -> manifest dict (only enabled, valid mods)
    :return: List of modID strings in load order
    """
    import heapq

    # -- Read dependency edges, ignoring bad values -----------------------------
    # parsed_refs[modID] is the dict {dep_modID: version_spec_or_None} parsed
    # straight from the manifest. deps[modID] is the set of dep modIDs (the keys
    # of parsed_refs[modID]); keeping both lets the version spec be checked
    # against the dependency's own manifest version.
    parsed_refs = {}
    for modID in sorted(manifests.keys()):
        raw = manifests[modID].get("dependencies") or []
        parsed_refs[modID] = _parse_dependency_list(raw, modID, "dependencies")
    deps = {modID: set(parsed.keys()) for modID, parsed in parsed_refs.items()}

    # -- Drop unsatisfiable mods (missing / disabled / transitively-skipped) ----
    # A mod is unsatisfiable if any of its dependencies is not loadable (missing,
    # disabled, or itself skipped) OR does not satisfy the declared version spec.
    # We resolve to a fixpoint so that mods which depend on a skipped mod are also
    # skipped — e.g. A -> B -> (missing), so B is skipped and A is skipped too.
    versions = {
        modID: str(manifests[modID].get("version", "0.0.0") or "0.0.0")
        for modID in manifests
    }
    loadable = set(manifests.keys())
    changed = True
    while changed:
        changed = False
        for modID in sorted(loadable):
            unavailable = []
            for dep in sorted(deps[modID]):
                dep_spec = parsed_refs[modID][dep]
                if dep not in loadable:
                    unavailable.append(dep)
                elif not _version_matches(dep_spec, versions[dep]):
                    unavailable.append(f"{dep} (requires {dep_spec}, found {versions[dep]})")
            if unavailable:
                print(f"\x1b[33m  Skipping mod '{modID}': depends on unavailable mod(s) {unavailable}\033[0m")
                loadable.discard(modID)
                changed = True

    # -- Topologically sort the loadable set ------------------------------------
    # Kahn's algorithm with an alphabetical heap for deterministic tie-breaking
    # (matches the old alphabetical order for mods with no dependencies).
    indegree = {modID: 0 for modID in loadable}
    dependents = {modID: [] for modID in loadable}  # modID -> mods that depend on it
    for modID in loadable:
        for dep in deps[modID]:
            # By the fixpoint above, every dependency of a loadable mod is loadable.
            dependents[dep].append(modID)
            indegree[modID] += 1

    ready = [modID for modID in loadable if indegree[modID] == 0]
    heapq.heapify(ready)
    order = []
    remaining = set(loadable)
    reported_cycles = set()  # frozensets of cycle groups already reported
    while remaining:
        if ready:
            modID = heapq.heappop(ready)
        else:
            # No ready mods left, but mods still remain -> at least one
            # dependency cycle exists among `remaining`. Report each distinct
            # cycle group exactly once (so independent cycles each get their own
            # warning), then break deterministically at the alphabetically-first
            # remaining mod so the load continues rather than stalling.
            for group in sorted(_cycle_groups(remaining, deps)):
                key = frozenset(group)
                if key not in reported_cycles:
                    print(f"\x1b[33m  Dependency cycle detected among: {group}; loading in alphabetical order\033[0m")
                    reported_cycles.add(key)
            modID = sorted(remaining)[0]
        order.append(modID)
        remaining.discard(modID)
        for dependent in dependents[modID]:
            if dependent in remaining:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    heapq.heappush(ready, dependent)

    return order


def _check_incompatibilities(manifests, loadable):
    """Detect declared incompatibilities among the mods that will actually load.

    A mod's manifest may declare an "incompatibilities" list of entries, each a
    modID (with an optional version spec) that this mod will NOT work alongside.
    If a loaded mod's version matches a dismissive entry, the two cannot coexist.

    This is fatal: rather than run with a broken combination, the loader raises
    ModIncompatibilityError listing ALL detected conflicts at once so the player
    can fix the manifest set in one go.

    :param manifests: dict of modID -> manifest dict (the enabled, valid mods)
    :param loadable: set of modIDs that will actually be loaded
    :raises ModIncompatibilityError: If any incompatibility is detected
    """
    versions = {
        modID: str(manifests[modID].get("version", "0.0.0") or "0.0.0")
        for modID in manifests
    }
    conflicts = []
    for modID in sorted(loadable):
        raw = manifests[modID].get("incompatibilities")
        if not raw:
            continue
        # Note: we parse incompatibilities here rather than up front, so a mod
        # that is itself skipped never raises — only mods that actually load can
        # produce conflicts.
        incompat = _parse_dependency_list(raw, modID, "incompatibilities")
        for other in sorted(incompat):
            if other not in loadable:
                # The conflicting mod isn't loaded, so there is nothing to clash with.
                continue
            spec = incompat[other]
            if spec is None or _version_matches(spec, versions[other]):
                if spec is None:
                    conflicts.append(f"'{modID}' is incompatible with '{other}'")
                else:
                    conflicts.append(f"'{modID}' (v{versions[modID]}) is incompatible with '{other}' v{versions[other]} (requires it to not match {spec})")
    if conflicts:
        raise ModIncompatibilityError(
            "\n  Detected incompatible mods:\n    " + "\n    ".join(conflicts)
        )


def load_mods(registry, game_state=None):
    """
    Scans MODS_DIR, loads each valid mod, and calls register(registry) on its backend module.
    Returns a list of loaded manifest dicts (for use by core.py to know which client.js to serve).

    While each mod loads, its manifest namespace is pushed onto the registry
    (and game state, if given) so unqualified names/keys auto-prefix with it.

    :param registry: Handler registry mods register against
    :param game_state: Optional game state to namespace during loading
    """
    if not os.path.isdir(MODS_DIR):
        print("No mods directory found, skipping mod loading")
        return []

    # -- Discover mods ---------------------------------------------------------
    # Read all manifests first so load order can be determined before any imports
    manifests = {}
    for mod_folder in os.listdir(MODS_DIR):
        mod_path = os.path.join(MODS_DIR, mod_folder)
        if not os.path.isdir(mod_path):
            continue
        manifest_path = os.path.join(mod_path, "manifest.json")
        if not os.path.isfile(manifest_path):
            print(f"\x1b[33mMod folder '{mod_folder}' has no manifest.json, skipping\033[0m")
            continue
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        manifest["_mod_path"] = mod_path  # stash path for later use

        # -- Disabled check ----------------------------------------------------
        # A mod can be turned "off" (not imported, not registered, and its
        # client.js not streamed) while keeping its files and code intact, by
        # setting "enabled": false in its manifest.json. Default is enabled so
        # existing mods without the field keep loading unchanged.
        if not manifest.get("enabled", True):
            print(f"\x1b[33mMod '{mod_folder}' is disabled in manifest, skipping\033[0m")
            continue

        try:
            manifest["_namespace"] = _get_namespace(manifest)
        except ValueError as e:
            print(f"\x1b[31m  {e}, skipping\033[0m")
            continue
        manifests[manifest["modID"]] = manifest

    # -- Load in order ---------------------------------------------------------
    # Determine load order FIRST (this prunes unavailable mods and detects
    # dependency cycles), then check for declared incompatibilities among the
    # mods that will actually load. An incompatibility is fatal and stops the
    # entire load, so the server refuses to start with a broken mod mix instead
    # of running partway.
    order = _load_order(manifests)
    _check_incompatibilities(manifests, set(order))

    loaded = []
    for modID in order:
        manifest = manifests[modID]
        mod_path = manifest["_mod_path"]
        namespace = manifest["_namespace"]
        backend_py = manifest.get("backend_py")

        print(f"Loading mod: {manifest['name']} v{manifest['version']} ({modID}) [namespace: {namespace}]")

        # Enter the mod's namespace for the whole backend load — every
        # unqualified op/handler name/state key inside register() (and any
        # module-level code) is prefixed with `namespace` automatically.
        registry.push_namespace(namespace)
        if game_state is not None:
            game_state.push_namespace(namespace)
        try:
            # backend_py is nullable — client-side-only mods skip this.
            # No backend_py in the manifest (absent or empty) means the mod is
            # client-side only, so there is nothing to register server-side and
            # no warning should be emitted (mirrors the silent client_js skip
            # in core._send_mod_scripts for server-side-only mods).
            if backend_py:
                py_path = os.path.join(mod_path, backend_py)
                if not os.path.isfile(py_path):
                    print(f"\x1b[33m  main.py '{backend_py}' not found for mod '{modID}'\033[0m")
                else:
                    # Dynamically import the mod's main.py without polluting sys.modules
                    # with a generic name — use modID as the module name
                    spec = importlib.util.spec_from_file_location(f"mod_{modID}", py_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Every backend mod must expose a register(registry) function
                    if not hasattr(module, "register"):
                        print(f"\x1b[33m  Mod '{modID}' has no register() function\033[0m")
                    else:
                        module.register(registry)
                    print(f"  Backend registered: {backend_py}")
            # else: no backend_py — mod is client-side only, skip silently.

            loaded.append(manifest)
            print(f"  Loaded OK")
        except Exception:
            # A failed load must not take the namespace stack down with it
            raise
        finally:
            registry.pop_namespace()
            if game_state is not None:
                game_state.pop_namespace()

    print(f"Mod loading complete: {len(loaded)} mod(s) loaded")
    return loaded