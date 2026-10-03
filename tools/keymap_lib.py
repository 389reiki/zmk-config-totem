"""Small helpers to read config/totem.keymap and the two keycode headers (no dependencies).

Used by tools/check_keymap.py, tools/make_keycode_list.py and keymap-drawer/draw.py.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYMAP = ROOT / "config" / "totem.keymap"
MAC_H = ROOT / "config" / "keys_de_mac.h"
WIN_H = ROOT / "config" / "keys_de_win.h"

N_KEYS = 38
FINGERS_L = ["pinky", "ring finger", "middle finger", "index finger", "inner index"]
FINGERS_R = ["inner index", "index finger", "middle finger", "ring finger", "pinky"]


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def defines(text):
    """#define NAME VALUE (single line) -> {NAME: VALUE}."""
    out = {}
    for m in re.finditer(r"^\s*#define\s+(\w+)\s+([^\n]*)$", text, flags=re.M):
        out[m.group(1)] = m.group(2).strip()
    return out


def expand(value, defs, depth=0):
    """Expand #define names inside a value (used for layer lists like MAC_LAYERS)."""
    if depth > 10:
        return value
    tokens = value.split()
    out = []
    for t in tokens:
        if t in defs and not re.fullmatch(r"\d+", t):
            out.extend(expand(defs[t], defs, depth + 1).split())
        else:
            out.append(t)
    return " ".join(out)


def split_bindings(text):
    return [re.sub(r"\s+", " ", b.strip()) for b in re.findall(r"&[^&]+", text)]


def block(text, name):
    """Content of the first `name { ... }` node (brace-matched), or None."""
    m = re.search(r"\b" + name + r"\s*\{", text)
    if not m:
        return None
    depth, i = 1, m.end()
    while depth and i < len(text):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return text[m.end():i - 1]


def read_keymap(path=KEYMAP):
    """Returns dict with:
    layers:  list of (node_name, display_name, [38 bindings]) in file order (= layer number)
    defs:    #defines from the keymap
    combos:  list of dicts {name, positions:[int], layers:[display names] or None, binding}
    conditional: list of (if_layer_display_names, then_layer_display_name)
    """
    text = strip_comments(path.read_text(encoding="utf-8"))
    defs = defines(text)

    layers = []
    for m in re.finditer(r"(\w+)\s*\{\s*display-name\s*=\s*\"([^\"]+)\";\s*bindings\s*=\s*<(.*?)>;", text, re.S):
        layers.append((m.group(1), m.group(2), split_bindings(m.group(3))))
    index_to_name = {i: l[1] for i, l in enumerate(layers)}

    def layer_names(value):
        names = []
        for t in expand(value, defs).split():
            num = int(defs.get(t, t)) if re.fullmatch(r"\d+", defs.get(t, t)) else None
            if num is not None and num in index_to_name:
                names.append(index_to_name[num])
        return names

    combos = []
    cblock = block(text, "combos")
    if cblock:
        for m in re.finditer(r"(\w+)\s*\{([^{}]*)\}", cblock):
            body = m.group(2)
            pos = re.search(r"key-positions\s*=\s*<([^>]*)>", body)
            bind = re.search(r"bindings\s*=\s*<([^>]*)>", body)
            lay = re.search(r"layers\s*=\s*<([^>]*)>", body)
            if not (pos and bind):
                continue
            combos.append({
                "name": m.group(1),
                "positions": [int(p) for p in pos.group(1).split()],
                "layers": layer_names(lay.group(1)) if lay else None,
                "binding": split_bindings(bind.group(1))[0],
            })

    conditional = []
    for m in re.finditer(r"if-layers\s*=\s*<([^>]*)>;\s*then-layer\s*=\s*<([^>]*)>;", text):
        conditional.append((layer_names(m.group(1)), layer_names(m.group(2))[0]))

    return {"layers": layers, "defs": defs, "combos": combos, "conditional": conditional}


def read_header(path):
    """keycode header -> (definitions {NAME: expression}, characters {NAME: character})."""
    defs, chars, cur = {}, {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        c = re.match(r"/\* (.+) \*/\s*$", line)
        if c:
            cur = c.group(1)
            continue
        d = re.match(r"#define (\w+) (.*)$", line)
        if d:
            defs[d.group(1)] = d.group(2).strip()
            if cur:
                chars[d.group(1)] = cur

    def resolve(name, depth=0):
        v = defs.get(name, name)
        a = re.fullmatch(r"\((\w+)\)", v)
        if a and a.group(1) in defs and depth < 10:
            return resolve(a.group(1), depth + 1)
        return v

    return {n: resolve(n) for n in defs}, chars


def describe(pos):
    """Human description of a key position, e.g. 'key 13 (left hand, home row, index finger)'."""
    if pos >= 32:
        side = "left" if pos <= 34 else "right"
        which = ["outer", "middle", "inner"][pos - 32] if pos <= 34 else ["inner", "middle", "outer"][pos - 35]
        return f"key {pos} ({side} thumb, {which})"
    if pos == 20:
        return "key 20 (left hand, bottom row, outer key)"
    if pos == 31:
        return "key 31 (right hand, bottom row, outer key)"
    if pos < 10:
        row, col = "top row", pos
    elif pos < 20:
        row, col = "home row", pos - 10
    else:  # 21-25 left, 26-30 right
        row, col = "bottom row", pos - 21
    side = "left" if col < 5 else "right"
    finger = FINGERS_L[col] if col < 5 else FINGERS_R[col - 5]
    return f"key {pos} ({side} hand, {row}, {finger})"
