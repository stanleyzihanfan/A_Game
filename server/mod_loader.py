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
    """Raised when two loaded mods declare an incompatibility.

    Carries the list of detected conflicts. The server treats a broken mod mix
    as fatal: it stops loading and refuses to start rather than running with
    mods that declared themselves incompatible.
    """

# -- Mod loader ----------------------------------------------------------------
# Scans the /mods directory, reads each manifest.json, and loads each mod's
# backend_py in order, calling register(registry) on each one.
# MODS_DIR is the absolute path to the /mods folder at project root.
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
    if not manifest.get("modID"):
        raise ValueError("Manifest has no 'modID'; cannot determine namespace")
    namespace = manifest.get("namespace") or manifest["modID"]
    if namespace == "core":
        raise ValueError(f"Mod '{manifest['modID']}' declares namespace 'core', which is reserved for the game engine")
    if ":" in namespace or not namespace.replace("_","").replace("-","").isalnum():
        raise ValueError(f"Mod '{manifest['modID']}' declares invalid namespace '{namespace}' (letters, digits, _ and - only, no ':')")
    return namespace


# -- Version handling ------------------------------------------------------------
# Version comparison is pluggable per-mod. A "version scheme" (identified by a
# string, stored in a mod's manifest as "version_scheme") turns a version string
# into a sortable key, and optionally matches a specifier against a version when
# the operators alone aren't enough. The scheme used to evaluate a dependency/
# incompatibility constraint is the TARGET mod's scheme, not the declaring mod's.
#
# Built-ins:
#   - 'pep440' (default): dotted numeric releases, optional pre-release suffix,
#     build metadata ignored. Handles '1.20.1', '1.20.1-pre1', '0.92.0+1.20.4'.
#   - 'mc': Minecraft-flavoured. All of the above, plus year-week snapshots
#     ('24w13a', '25w02a'), a leading 'v' ('v1.20.1'), loader prefixes
#     ('forge-45.2.0', 'fabric-0.92.0+1.20.4'), combined MC+loader versions
#     ('1.20.4-0.92.0'), and Maven-style ranges ('[1.20.1,1.21)', '(,1.21]').
#
# Custom: a mod may set "version_scheme" to a name registered at runtime, or
# point at a file that provides its own scheme class (see _resolve_scheme).


class _PEP440Scheme:
    """PEP-440-lite version parsing/specifier matching (the default scheme)."""

    name = "pep440"

    @staticmethod
    def parse(v):
        """Return a sortable, comparable key for `v`.

        Supports dotted numeric releases and an optional pre-release suffix
        (e.g. '1.2.3-beta.1'). Build metadata after '+' is ignored. Missing
        components are treated as 0, so '1.2' == '1.2.0'. A pre-release sorts
        BEFORE its final release, so 1.0.0-beta < 1.0.0.

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

    @staticmethod
    def release_with_count(v):
        """Return (release_tuple_3, segment_count) for the '~=' upper bound."""
        v = str(v).strip().split("+", 1)[0]
        m = re.match(r"^(\d+(?:\.\d+)*)", v)
        if not m:
            raise ValueError(f"Unrecognized version string: {v!r}")
        nums = [int(x) for x in m.group(1).split(".")]
        count = len(nums)
        while len(nums) < 3:
            nums.append(0)
        return (tuple(nums), count)

    @classmethod
    def compatible_release(cls, base_spec, version):
        """PEP-440 '~=' (compatible release): >=X.Y.Z and <X.(Y+1).0"""
        base, count = cls.release_with_count(base_spec)
        target, _ = cls.release_with_count(version)
        if target < base:
            return False
        if count == 1:
            upper = (base[0] + 1, 0, 0)
        else:
            upper_list = list(base[:count - 1])
            upper_list[-1] += 1
            upper = (tuple(upper_list) + (0, 0, 0))[:3]
        return target < upper

    @classmethod
    def matches_specifier(cls, spec, version):
        """Return True if `version` satisfies the single clause `spec`."""
        spec = spec.strip()
        if not spec or spec == "*":
            return True
        m = re.match(r"^(==|!=|>=|<=|>|<|~=)?\s*(.+)$", spec)
        if not m:
            raise ValueError(f"Unrecognized version specifier: {spec!r}")
        op = m.group(1) or "=="
        base = m.group(2).strip()
        try:
            v = cls.parse(version)
            b = cls.parse(base)
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
                return cls.compatible_release(base, version)
            except ValueError:
                return False
        return False


class _MinecraftScheme(_PEP440Scheme):
    """Minecraft-flavoured version scheme.

    Accepts everything PEP-440-lite does, plus the conventions common in the
    Minecraft modding ecosystem:
      - year-week snapshots: '24w13a', '25w02a' (ordered by year, then week,
        then the trailing letter a/b/c ...)
      - a leading 'v': 'v1.20.1'
      - loader prefixes: 'forge-45.2.0', 'fabric-0.92.0+1.20.4'
      - combined MC+loader versions: '1.20.4-0.92.0'
      - Maven-style version ranges as a specifier: '[1.20.1,1.21)', '(,1.21]'
    """

    name = "mc"

    @classmethod
    def parse(cls, v):
        v = str(v).strip().split("+", 1)[0]
        # Strip a leading 'v' (case-insensitive).
        s = v.lstrip("vV")
        # Remove a leading loader prefix (e.g. 'forge-', 'fabric-'); if after
        # removing it the remainder is a dotted numeric or snapshot, use it.
        m = re.match(r"^[A-Za-z][A-Za-z0-9]*-", s)
        if m:
            rest = s[m.end():]
            if not re.match(r"^\d{2}w\d{2}[a-z]?$", rest):
                s = rest
        # Minecraft snapshot: YYwWWx (e.g. '24w13a'). A two-digit year >= 20 maps
        # to 20xx, so '24w13a' -> (2024, 13, snap-'a').
        ms = re.match(r"^(\d{2})w(\d{2})([a-z]?)$", s)
        if ms:
            yy = int(ms.group(1))
            year = yy + 2000 if yy >= 20 else yy
            return ((year, int(ms.group(2)), 0), 0, "snap" + ms.group(3))
        # Otherwise: keep the FIRST dotted numeric group as the release. A
        # combined version like '1.20.4-0.92.0' (MC + loader) thus sorts with
        # '1.20.4'; a letter-suffixed pre-release like '1.20.1-pre1' keeps the
        # suffix so PEP-440 pre-release ordering still applies.
        pm = re.match(r"^(\d+(?:\.\d+)*)", s)
        if not pm:
            # Didn't even start with a number — fall through to PEP-440 (which
            # raises a clear "unrecognized" error the caller treats as an
            # unsatisfied gate).
            return super().parse(s)
        primary = pm.group(1)
        trailing = s[pm.end():]
        if trailing:
            # Only treat it as a pre-release if the suffix starts with a letter
            # (e.g. '-pre1', '-rc1', '-alpha', '.beta'). A trailing dotted
            # numeric (a secondary/loader version) is dropped.
            if re.match(r"^[.\-][A-Za-z]", trailing):
                return super().parse(s)
            s = primary
        return super().parse(s)

    @classmethod
    def matches_specifier(cls, spec, version):
        """Match a clause, additionally supporting Maven-style ranges.

        A clause may be a PEP-440 operator ('>=1.20.1'), a bare version, or a
        Maven-style interval: '[a,b]', '(a,b)', '[a,b)', '(,b]', '[a,)'. A
        bracket is inclusive, a paren is exclusive; a missing edge is unbounded.
        """
        spec = spec.strip()
        if not spec or spec == "*":
            return True
        if spec[0] in "[(" and spec[-1] in ")]":
            return cls._match_interval(spec, version)
        return super().matches_specifier(spec, version)

    @classmethod
    def _match_interval(cls, spec, version):
        low_inc = spec[0] == "["
        high_inc = spec[-1] == "]"
        body = spec[1:-1]
        parts = body.split(",", 1)
        if len(parts) == 1:
            # '[1.20.1]' -- exact
            low = parts[0].strip()
            high = low
            return cls._version_gt(version, low, low_inc) and cls._version_gt(high, version, high_inc)
        low, high = parts[0].strip(), parts[1].strip()
        if low and not cls._version_gt(version, low, low_inc):
            return False
        if high and not cls._version_gt(high, version, high_inc):
            return False
        return True

    @classmethod
    def _version_gt(cls, a, b, inclusive):
        """Return True if a is >= b (inclusive) or > b (exclusive)."""
        try:
            ka, kb = cls.parse(a), cls.parse(b)
        except ValueError:
            return False
        if ka == kb:
            return inclusive
        return ka > kb


# -- Scheme registry --------------------------------------------------------------
# name -> scheme class. A scheme is any object exposing:
#   parse(v) -> comparable key (raises ValueError on unparseable)
#   matches_specifier(spec, version) -> bool
# Built-ins registered here; custom schemes can be added at runtime via
# register_version_scheme() (from a mod's own code).


_VERSION_SCHEMES = {
    "pep440": _PEP440Scheme,
    "mc": _MinecraftScheme,
}


def register_version_scheme(name, scheme_class):
    """Register a custom version scheme for use in manifests.

    :param name: The scheme identifier mods will put in 'version_scheme'
    :param scheme_class: An object exposing parse(v) and matches_specifier(s, v)
    """
    _VERSION_SCHEMES[name] = scheme_class


def _get_scheme(name):
    """Look up a scheme by name; unknown names fall back to the default.

    :param name: Scheme identifier (or None)
    :return: scheme class
    """
    if name is None:
        return _PEP440Scheme
    return _VERSION_SCHEMES.get(name, _PEP440Scheme)


def _resolve_scheme(manifest, mods_dir=MODS_DIR):
    """Resolve the version scheme a mod uses, from its manifest.

    The "version_scheme" field can be:
      - a built-in/registered scheme name (e.g. "pep440", "mc"); or
      - a path to a Python file defining a scheme, relative to the mod folder
        (e.g. "version_scheme.py"). The file must expose a module-level
        `scheme` object with `parse(v)` and `matches_specifier(s, v)`.

    An unknown scheme name, or a custom file that fails to load, falls back to
    the default PEP-440 scheme with a warning, so a bad scheme never crashes the
    load (though it may cause version gates to behave conservatively).

    :param manifest: The mod's manifest dict
    :param mods_dir: Absolute path to the mods directory (for relative file paths)
    :return: scheme class
    """
    raw = manifest.get("version_scheme")
    if not raw:
        return _PEP440Scheme
    # If it looks like a file path (has .py or a slash), load it as a custom scheme.
    if isinstance(raw, str) and (raw.endswith(".py") or "/" in raw or "\\" in raw):
        base = manifest.get("_mod_path") or mods_dir
        scheme_file = raw if os.path.isabs(raw) else os.path.join(base, raw)
        if os.path.isfile(scheme_file):
            try:
                spec = importlib.util.spec_from_file_location(f"mod_{manifest['modID']}_scheme", scheme_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                scheme = getattr(module, "scheme", None) or getattr(module, "version_scheme", None)
                if scheme is None:
                    print(f"\x1b[33m  Mod '{manifest['modID']}' version_scheme file '{raw}' has no 'scheme' object, using default\033[0m")
                    return _PEP440Scheme
                return scheme
            except Exception as e:
                print(f"\x1b[33m  Mod '{manifest['modID']}' version_scheme file '{raw}' failed to load ({e}), using default\033[0m")
                return _PEP440Scheme
        print(f"\x1b[33m  Mod '{manifest['modID']}' version_scheme file '{raw}' not found, using default\033[0m")
        return _PEP440Scheme
    # Otherwise treat it as a scheme name.
    if raw not in _VERSION_SCHEMES:
        print(f"\x1b[33m  Mod '{manifest['modID']}' has unknown version_scheme '{raw}', using default\033[0m")
        return _PEP440Scheme
    return _VERSION_SCHEMES[raw]


def _version_matches(spec, version, scheme=None):
    """Return True if `version` satisfies `spec` under the given scheme class.

    If the scheme cannot parse `version` (or the spec), the constraint is treated
    as NOT satisfied (returns False) — the caller then warns and blocks the
    dependent mod rather than guessing. This is the "warn + block" fail mode.

    :param spec: version spec string or None (None matches anything)
    :param version: installed version string
    :param scheme: a version scheme class (defaults to the PEP-440 scheme)
    :return: bool
    """
    if spec is None:
        return True
    spec = str(spec).strip()
    if not spec or spec == "*":
        return True
    scheme = scheme or _PEP440Scheme
    for clause in spec.split(","):
        clause = clause.strip()
        if clause:
            try:
                if not scheme.matches_specifier(clause, version):
                    return False
            except ValueError:
                # Unparseable under this scheme -> cannot prove satisfaction.
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

    This lets the loader report each independent cycle separately (e.g. a<->b and
    c<->d are two distinct groups), instead of lumping every stuck mod into one
    message.

    :param remaining: set of modIDs still not ordered
    :param deps: dict of modID -> set of modIDs it depends on (loadable only)
    :return: list of sorted lists, each a distinct cycle group
    """
    # Tarjan's SCC algorithm, on the subgraph induced by `remaining`.
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
    """Return mod folders in load order, topologically sorted by dependencies.

    A mod's manifest may declare a "dependencies" list of modID strings. Every
    dependency is guaranteed to load BEFORE the mod that depends on it, so a mod
    can rely on the handlers / state its dependencies registered during their own
    register(). Mods with no dependencies keep their old alphabetical order, so
    the result stays deterministic and unchanged for existing mods.

    Failure handling (consistent with the loader's warn-and-skip philosophy; a
    config problem never crashes the whole load):
      - A mod that depends on a modID that will NOT be loaded — because it is
        missing, disabled (enabled:false), or itself skipped — is skipped with a
        warning. This cascades: mods that depend on a skipped mod are skipped too.
      - A dependency whose declared version spec is NOT satisfied by the
        dependency's manifest version is skipped with a warning (and cascades).
      - Dependency cycles are detected and broken deterministically at the
        alphabetically-first mod of each cycle, with a warning. Each distinct
        (strongly connected) cycle group is reported separately.
      - A self-dependency is ignored with a warning.
      - A non-list or non-string "dependencies" value is ignored with a warning.

    :param manifests: dict of modID -> manifest dict (only enabled, valid mods)
    :return: List of modID strings in load order
    """
    import heapq

    # Read dependency edges, ignoring bad values. parsed_refs[modID] is the dict
    # {dep_modID: version_spec_or_None} parsed from the manifest; deps[modID] is
    # the set of dep modIDs (the keys of parsed_refs[modID]).
    parsed_refs = {}
    for modID in sorted(manifests.keys()):
        raw = manifests[modID].get("dependencies") or []
        parsed_refs[modID] = _parse_dependency_list(raw, modID, "dependencies")
    deps = {modID: set(parsed.keys()) for modID, parsed in parsed_refs.items()}

    # Drop unsatisfiable mods (missing / disabled / transitively-skipped). A mod
    # is unsatisfiable if any dependency is not loadable OR does not satisfy the
    # declared version spec. Resolve to a fixpoint so mods depending on a skipped
    # mod are also skipped.
    versions = {
        modID: str(manifests[modID].get("version", "0.0.0") or "0.0.0")
        for modID in manifests
    }
    # Resolve each mod's version scheme once. The scheme used to evaluate a
    # dependency's version gate is the DEPENDENCY's scheme, not the declaring mod's.
    schemes = {
        modID: _resolve_scheme(manifests[modID])
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
                elif not _version_matches(dep_spec, versions[dep], schemes[dep]):
                    unavailable.append(f"{dep} (requires {dep_spec}, found {versions[dep]})")
            if unavailable:
                print(f"\x1b[33m  Skipping mod '{modID}': depends on unavailable mod(s) {unavailable}\033[0m")
                loadable.discard(modID)
                changed = True

    # Topologically sort the loadable set. Kahn's algorithm with an alphabetical
    # heap for deterministic tie-breaking (matches the old alphabetical order for
    # mods with no dependencies).
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
            # No ready mods but mods still remain -> at least one dependency
            # cycle exists among `remaining`. Report each distinct cycle group
            # once, then break deterministically at the alphabetically-first
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
    # Use each conflicting mod's OWN scheme for its version gate, so a mod
    # declaring "incompatibilities": ["foo>=24w13a"] checks foo as MC if foo says
    # it uses the MC scheme.
    schemes = {
        modID: _resolve_scheme(manifests[modID])
        for modID in manifests
    }
    conflicts = []
    for modID in sorted(loadable):
        raw = manifests[modID].get("incompatibilities")
        if not raw:
            continue
        # Parse incompatibilities here rather than up front, so a mod that is
        # itself skipped never raises — only mods that actually load can conflict.
        incompat = _parse_dependency_list(raw, modID, "incompatibilities")
        for other in sorted(incompat):
            if other not in loadable:
                # The conflicting mod isn't loaded, so there is nothing to clash with.
                continue
            spec = incompat[other]
            if spec is None or _version_matches(spec, versions[other], schemes[other]):
                if spec is None:
                    conflicts.append(f"'{modID}' is incompatible with '{other}'")
                else:
                    conflicts.append(f"'{modID}' (v{versions[modID]}) is incompatible with '{other}' v{versions[other]} (requires it to not match {spec})")
    if conflicts:
        raise ModIncompatibilityError(
            "\n  Detected incompatible mods:\n    " + "\n    ".join(conflicts)
        )


def load_mods(registry, game_state=None):
    """Scan MODS_DIR, load each valid mod, and call register(registry) on its backend.

    Returns a list of loaded manifest dicts (for use by core.py to know which
    client.js to serve). While each mod loads, its manifest namespace is pushed
    onto the registry (and game state, if given) so unqualified names/keys
    auto-prefix with it.

    :param registry: Handler registry mods register against
    :param game_state: Optional game state to namespace during loading
    """
    if not os.path.isdir(MODS_DIR):
        print("No mods directory found, skipping mod loading")
        return []

    # Discover mods: read all manifests first so load order can be determined
    # before any imports.
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

        # Disabled check: a mod can be turned off (not imported, not registered,
        # its client.js not streamed) while keeping its files intact, by setting
        # "enabled": false in its manifest.json. Default is enabled.
        if not manifest.get("enabled", True):
            print(f"\x1b[33mMod '{mod_folder}' is disabled in manifest, skipping\033[0m")
            continue

        try:
            manifest["_namespace"] = _get_namespace(manifest)
        except ValueError as e:
            print(f"\x1b[31m  {e}, skipping\033[0m")
            continue
        manifests[manifest["modID"]] = manifest

    # Load in order. Determine load order FIRST (prunes unavailable mods and
    # detects cycles), then check for declared incompatibilities among the mods
    # that will actually load. An incompatibility is fatal and stops the entire
    # load, so the server refuses to start with a broken mod mix.
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
        # unqualified op/handler/state key inside register() is prefixed
        # with `namespace` automatically.
        registry.push_namespace(namespace)
        if game_state is not None:
            game_state.push_namespace(namespace)
        try:
            # backend_py is nullable — client-side-only mods skip this (no
            # warning, mirroring the silent client_js skip in core.py).
            if backend_py:
                py_path = os.path.join(mod_path, backend_py)
                if not os.path.isfile(py_path):
                    print(f"\x1b[33m  main.py '{backend_py}' not found for mod '{modID}'\033[0m")
                else:
                    # Dynamically import the mod's main.py without polluting
                    # sys.modules — use modID as the module name.
                    spec = importlib.util.spec_from_file_location(f"mod_{modID}", py_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Every backend mod must expose a register(registry) function
                    if not hasattr(module, "register"):
                        print(f"\x1b[33m  Mod '{modID}' has no register() function\033[0m")
                    else:
                        module.register(registry)
                    print(f"  Backend registered: {backend_py}")

            loaded.append(manifest)
            print(f"  Loaded OK")
        except Exception:
            # A failed load must not take the namespace stack down with it.
            raise
        finally:
            registry.pop_namespace()
            if game_state is not None:
                game_state.pop_namespace()

    print(f"Mod loading complete: {len(loaded)} mod(s) loaded")
    return loaded