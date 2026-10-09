#!/usr/bin/env python3
"""Draw the TOTEM keymap with keymap-drawer (one SVG per layer + one overview).

Run from the repo root:  python keymap-drawer/draw.py
Needs: pip install keymap-drawer==0.21.0 tree-sitter==0.24.0 tree-sitter-devicetree==0.14.1

What it does:
  1. Copies config/totem.keymap without the two locale #includes, so keycodes like DE_AT
     stay readable instead of being expanded to raw HID codes.
  2. Builds a label map (DE_AT -> @) from the comments in config/keys_de_mac.h.
  3. Parses the keymap, keeps the macOS layers only (the Windows overlays put the same
     functions on the same keys) and writes function labels where a keystroke alone is unclear.
     Modifier labels read "Mac/Windows", e.g. Cmd/Ctrl. Which key opens which layer is read from
     the keymap itself, so moving keys needs no change in this file.
  4. Draws with the real TOTEM geometry (totem_layout.json, from docs/images/TOTEM_layout.svg)
     and the layer colours: Nav blue, Sym green, Num amber, Sys grey, combos purple.
"""
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from keymap_lib import read_keymap  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "keymap-drawer"
OUT = HERE / "svg"
TMP = HERE / ".tmp"

MAC_LAYERS = ["BASE", "NAV", "SYM", "NUM", "SYS"]
COLOR = {"NAV": "#378ADD", "SYM": "#1D9E75", "NUM": "#BA7517", "SYS": "#888780"}
# flag layers that switch a visible layer on (Space holds NAV_HOLD, which turns NAV on)
ALIAS = {"NAV_HOLD": "NAV"}
COMBO = "#7F77DD"

# Mac/Windows modifier names
MODS = {"LGUI": "Cmd/Ctrl", "LALT": "Opt/Alt", "LCTRL": "Ctrl/Win", "LSHFT": "Shift"}

# Labels for bindings whose keystroke alone does not say what they do (macOS keystrokes)
RAW = {
    "&bspc_del": {"t": "⌫", "s": "Del"},
    "&bsw LA(BSPC) 0": {"t": "⌫", "s": "⇧ Del", "h": "Wort ⌫"},
    "&swapper_mac": "App ⇄",
    "&sqt_dqt": {"t": "'", "s": '"'},
    "&tilde_mac": "~",
    "&caret_mac": "^",
    "&host_mac": {"t": "Mac", "s": "BT 0"},
    "&host_win": {"t": "Win", "s": "BT 1"},
    "&sk LSHFT": {"t": "Shift", "s": "1×"},
    "&sym_key SYM SYM": {"t": "Sym 1×", "h": "Sym"},
    "&num_key NUM NUM": {"t": "NumWord", "h": "Num"},
    "&lt_spc NAV_HOLD SPACE": {"t": "␣", "h": "Nav"},
    "&tog NAV_LOCK": {"t": "Nav fest", "h": "an/aus"},
    "&mo SYS": {"t": "Sys", "h": "halten"},
    "&kp LG(LS(DE_N4))": "Scrnsht",
    "&kp LG(TAB)": "App ⇄",
    "&kp LC(LS(TAB))": "Tab ←",
    "&kp LC(TAB)": "Tab →",
    "&kp LA(LEFT)": "Word ←",
    "&kp LA(RIGHT)": "Word →",
    "&kp LA(BSPC)": "Del word",
    "&kp PG_UP": "PgUp",
    "&kp PG_DN": "PgDn",
    "&kp RET": "↵",
    "&kp BSPC": "⌫",
    "&kp DEL": "Del",
    "&kp ESC": "Esc",
    "&kp TAB": "Tab",
    "&kp LG(DE_Z)": "Undo",
    "&kp LG(DE_X)": "Cut",
    "&kp LG(DE_C)": "Copy",
    "&kp LG(DE_V)": "Paste",
    "&kp LG(LS(DE_Z))": "Redo",
    "&bt BT_SEL 2": "BT 2",
    "&bt BT_SEL 3": "BT 3",
    "&bt BT_CLR": "BT clear",
    "&out OUT_TOG": "USB/BT",
    "&bootloader": "Boot",
    "&mkp LCLK": "Click L",
    "&mkp RCLK": "Click R",
    "&mkp MCLK": "Click M",
    "&mkp MB4": "Back",
    "&kp LG(DE_LBKT)": "Zurück",
    "&kp LG(DE_RBKT)": "Vor",
    "&kp LS(TAB)": "App ⇠",
    "&mkp MB5": "Fwd",
    "&mmv MOVE_LEFT": "Maus ←",
    "&mmv MOVE_UP": "Maus ↑",
    "&mmv MOVE_DOWN": "Maus ↓",
    "&mmv MOVE_RIGHT": "Maus →",
    "&msc SCRL_UP": "Scroll ↑",
    "&msc SCRL_DOWN": "Scroll ↓",
    "&msc SCRL_LEFT": "Scroll ←",
    "&msc SCRL_RIGHT": "Scroll →",
    "&kp C_PP": {"t": "⏯\ufe0e", "h": "Play/Pause"},
    "&kp C_PREV": {"t": "⏮\ufe0e", "h": "Titel zurück"},
    "&kp C_NEXT": {"t": "⏭\ufe0e", "h": "Titel vor"},
    "&kp C_VOL_UP": {"t": "Lauter", "h": "Lautstärke"},
    "&kp C_VOL_DN": {"t": "Leiser", "h": "Lautstärke"},
    "&sys_reset": "Reset",
}
# Same keystroke on the Mac, different job: named after the Windows twin key (nav_win_layer)
# Shift variants shown on the base layer (they are not on SYM)
BASE_SHIFTED = {"&kp DE_COMMA": ";", "&kp DE_DOT": ":"}
AMBIGUOUS = {"&kp LG(LEFT)", "&kp LG(RIGHT)"}
BY_WIN_TWIN = {"&kp HOME": "Home", "&kp END": "End", "&kp LA(LEFT)": "Back", "&kp LA(RIGHT)": "Fwd"}


def layer_keys(km):
    """Which key opens which layer – read from the keymap, so moving a key needs no change here.
    Returns (trig, held): trig[(layer, pos)] = layer it opens; held[layer] = {pos: label}."""
    layers = {l[1]: l[2] for l in km["layers"]}
    trig = {}
    for lay in MAC_LAYERS:
        for pos, b in enumerate(layers[lay]):
            parts = b.split()
            if parts[0] in ("&host_mac", "&host_win"):
                continue
            args = [ALIAS.get(a, a) for a in parts[1:]]
            for target in COLOR:
                if target in args:
                    trig[(lay, pos)] = target
    held = {}
    for target in COLOR:
        held[target] = {pos: target.capitalize() for (lay, pos), t in trig.items()
                        if t == target and lay in ("BASE", target)}
    for if_layers, then_layer in km["conditional"]:
        if then_layer in COLOR and not held[then_layer]:
            for l in if_layers:
                held[then_layer].update(held.get(l, {}))
    trig = {k: v for k, v in trig.items() if k[0] != v}
    return trig, held


def label_map():
    """DE_* keycode -> character, read from the comments in keys_de_mac.h."""
    m, cur = {}, None
    for line in (ROOT / "config" / "keys_de_mac.h").read_text(encoding="utf-8").splitlines():
        c = re.match(r"/\* (.+) \*/\s*$", line)
        if c:
            cur = c.group(1)
            continue
        d = re.match(r"#define (DE_[A-Z0-9_]+) ", line)
        if d and cur:
            m[d.group(1)] = cur
    m.update({"DE_A_UMLAUT": "ä", "DE_O_UMLAUT": "ö", "DE_U_UMLAUT": "ü", "SPACE": "␣",
              "UP": "↑", "DOWN": "↓", "LEFT": "←", "RIGHT": "→"})
    return m


CSS = """
rect.key { stroke-width: 1; }
text { font-size: 15px; }
text.hold, text.shifted { font-size: 10px; }
rect.combo { fill: %(combo)s; fill-opacity: .35; stroke: %(combo)s; }
""" % {"combo": COMBO}
for name, col in COLOR.items():
    CSS += f"""
.layer-{name} rect.key.lay {{ fill: {col}; fill-opacity: .22; stroke: {col}; }}
rect.key.trig-{name} {{ fill: {col}; fill-opacity: .45; stroke: {col}; }}
rect.key.held.trig-{name} {{ stroke-width: 4; }}
"""


def run(*args):
    subprocess.run(args, check=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)

    keymap = (ROOT / "config" / "totem.keymap").read_text(encoding="utf-8")
    keymap = re.sub(r'^#include "keys_de_[a-z]+\.h".*$', "", keymap, flags=re.M)
    (TMP / "totem.keymap").write_text(keymap, encoding="utf-8")

    cfg = {
        "parse_config": {
            "zmk_keycode_map": {**label_map(), **MODS},
            "raw_binding_map": RAW,
            "trans_legend": {"t": "▽", "type": "trans"},
        },
        "draw_config": {
            "dark_mode": "auto",
            "shrink_wide_legends": 5,
            "svg_extra_style": CSS,
            "key_w": 60,
            "key_h": 56,
            "combo_w": 36,
            "combo_h": 22,
        },
    }
    cfg_path = TMP / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    parsed = TMP / "parsed.yaml"
    with parsed.open("w", encoding="utf-8") as f:
        subprocess.run(["keymap", "-c", str(cfg_path), "parse", "-z", str(TMP / "totem.keymap")],
                       check=True, stdout=f)
    data = yaml.safe_load(parsed.read_text(encoding="utf-8"))

    km = read_keymap()
    raw_layers = {l[1]: l[2] for l in km["layers"]}
    trig, held = layer_keys(km)

    layers = {}
    for name in MAC_LAYERS:
        keys = []
        for pos, k in enumerate(data["layers"][name]):
            k = dict(k) if isinstance(k, dict) else {"t": k}
            raw = raw_layers[name][pos]
            twin = raw_layers.get(name + " WIN", [None] * 38)[pos]
            if raw in AMBIGUOUS and twin in BY_WIN_TWIN:
                k["t"] = BY_WIN_TWIN[twin]
            if name == "BASE" and raw in BASE_SHIFTED:   # show the Shift variant of , . on the base layer
                k["s"] = BASE_SHIFTED[raw]
            types = set(str(k.get("type", "")).split())
            if name != "BASE" and "trans" not in types and k.get("t") not in ("", None):
                types.add("lay")
            if (name, pos) in trig:          # key that opens another layer: that layer's colour
                types.discard("lay")
                types.add(f"trig-{trig[(name, pos)]}")
            if name in held and pos in held[name]:   # key held to reach this layer: thick border
                types.difference_update({"lay", "trans"})
                types.update({"held", f"trig-{name}"})
                k["t"] = held[name][pos]
            k["type"] = " ".join(sorted(t for t in types if t))
            if not k["type"]:
                del k["type"]
            keys.append(k)
        layers[name] = keys

    combos = []
    for c in data.get("combos", []):
        ls = c.get("l")
        if ls and not any(l in MAC_LAYERS for l in ls):
            continue  # Windows-only copy of a combo
        c = dict(c)
        c["l"] = ["BASE"]
        c["type"] = "combo"
        combos.append(c)

    drawn = TMP / "drawn.yaml"
    drawn.write_text(yaml.safe_dump({"layout": {"qmk_info_json": str(HERE / "totem_layout.json")},
                                     "layers": layers, "combos": combos},
                                    allow_unicode=True, sort_keys=False), encoding="utf-8")

    def draw(target, *extra):
        with target.open("w", encoding="utf-8") as f:
            subprocess.run(["keymap", "-c", str(cfg_path), "draw", str(drawn), *extra], check=True, stdout=f)
        svg = target.read_text(encoding="utf-8")
        # GitHub renders SVGs small; double the declared size (viewBox unchanged)
        svg = re.sub(r'<svg width="(\d+)" height="(\d+)"',
                     lambda m: f'<svg width="{2*int(m.group(1))}" height="{2*int(m.group(2))}"', svg, count=1)
        target.write_text(svg, encoding="utf-8")

    for name in MAC_LAYERS:
        draw(OUT / f"{name.lower()}.svg", "-s", name)
    draw(OUT / "totem.svg")
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("*.svg"))))


if __name__ == "__main__":
    sys.exit(main())
