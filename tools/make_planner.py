#!/usr/bin/env python3
"""Builds planner/totem-planer.html (drag-and-drop keymap planner) from config/totem.keymap.

Run from the repo root:  python tools/make_planner.py      (needs: pip install pyyaml)
The GitHub build runs this after every keymap change, so the planner always shows the current keymap.
Open planner/totem-planer.html in any browser; nothing is installed and nothing is sent anywhere.

What it does: reads the macOS layers and combos, turns each binding into a short label (same labels
as the diagrams in keymap-drawer/draw.py, plus German names), and fills planner/template.html.
The draft you make in the planner is kept in your browser only; it is reset when the keymap changes.
"""
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from keymap_lib import ROOT, read_keymap  # noqa: E402

TEMPLATE = ROOT / "planner" / "template.html"
OUT = ROOT / "planner" / "totem-planer.html"
GEOMETRY = ROOT / "keymap-drawer" / "totem_layout.json"
IDEAS = ROOT / "docs" / "ideen.md"
PLANNED = ROOT / "docs" / "vorgemerkt.md"
LAYERS = ["BASE", "NAV", "SYM", "NUM", "SYS"]

# labels from the diagram script (DE_* characters and special bindings)
_spec = importlib.util.spec_from_file_location("draw", ROOT / "keymap-drawer" / "draw.py")
_draw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_draw)
CHARS = _draw.label_map()
RAW = _draw.RAW

MOD_NAME = {"LGUI": "Cmd", "LALT": "Opt", "LCTRL": "Ctrl", "LSHFT": "Shift",
            "RGUI": "Cmd", "RALT": "Opt", "RCTRL": "Ctrl", "RSHFT": "Shift"}
MOD_FN = {"LG": "Cmd", "LA": "Opt", "LC": "Ctrl", "LS": "Shift", "RA": "Opt"}
KEY_NAME = {"PG_UP": "PgUp", "PG_DN": "PgDn", "RET": "↵", "BSPC": "⌫", "DEL": "Del", "ESC": "Esc",
            "TAB": "Tab", "HOME": "Home", "END": "End", "PSCRN": "PrtSc"}
GERMAN = {"Word ←": "Wort ←", "Word →": "Wort →", "Del word": "Wort ⌫", "Back": "Zurück", "Fwd": "Vor",
          "BT clear": "BT lösch",
          "Click L": "Klick L", "Click R": "Klick R", "Click M": "Klick M", "App ⇄": "App ⇢"}
# small second label: "⇧ x" = with Shift, otherwise = when held
SECOND = {"&bspc_del": "⇧ Del", "&sqt_dqt": '⇧ "', "&kp LG(DE_LBKT)": "Cmd+[", "&kp LG(DE_RBKT)": "Cmd+]"}
# Shift variants shown on the base layer only (they are not on SYM)
BASE_SHIFTED = {"&kp DE_COMMA": "⇧ ;", "&kp DE_DOT": "⇧ :"}
# keys whose macOS keystroke is ambiguous: named after their Windows twin (as in the diagrams)
BY_WIN_TWIN = {"&kp HOME": "Home", "&kp END": "End", "&kp LA(LEFT)": "Zurück", "&kp LA(RIGHT)": "Vor"}


COMBO_NAME = {"&kp RET": "Enter ↵", "&kp C_PREV": "Titel zurück", "&kp C_NEXT": "Titel vor"}
LEFT = {0, 1, 2, 3, 4, 10, 11, 12, 13, 14, 20, 21, 22, 23, 24, 25, 32, 33, 34}


def key_name(k):
    m = re.fullmatch(r"(L[GACS]|RA)\((.*)\)", k)
    if m:
        return MOD_FN[m.group(1)] + "+" + key_name(m.group(2))
    return CHARS.get(k) or MOD_NAME.get(k) or KEY_NAME.get(k, k)


def label(b):
    if b in RAW:
        r = RAW[b]
        if isinstance(r, str):
            out = {"t": GERMAN.get(r, r)}
        else:
            out = {"t": GERMAN.get(r.get("t", ""), r.get("t", ""))}
            if r.get("h"):
                out["h"] = r["h"]
            elif r.get("s"):
                out["h"] = r["s"]
    else:
        p = b.split()
        if p[0] == "&trans":
            return {"t": "", "trans": True}
        if p[0] == "&none":
            return {"t": "", "none": True}
        if p[0] == "&kp":
            out = {"t": key_name(p[1])}
        elif p[0] in ("&hml", "&hmr"):
            out = {"t": key_name(p[2]), "h": MOD_NAME.get(p[1], p[1])}
        else:
            out = {"t": b}
    if b in SECOND:
        out["h"] = SECOND[b]
    return out


def md_to_html(md):
    """Tiny Markdown subset for docs/ideen.md: headings, bullet lists, paragraphs, **bold**, *italic*, `code`."""
    import html as h

    def inline(s):
        s = h.escape(s, quote=False)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        return s

    out, in_list = [], False
    for line in md.splitlines():
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append("<li>" + inline(line[2:]) + "</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.startswith("## "):
            out.append("<h3>" + inline(line[3:]) + "</h3>")
        elif line.startswith("# "):
            continue  # page title is the tab itself
        elif line.strip():
            out.append("<p>" + inline(line) + "</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def stand():
    try:
        return subprocess.run(["git", "log", "-1", "--format=%cd", "--date=format:%d.%m.%Y %H:%M",
                               "--", "config/totem.keymap"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip() or "unbekannt"
    except Exception:
        return "unbekannt"


def main():
    km = read_keymap()
    layers = {l[1]: l[2] for l in km["layers"]}
    data = {"geometry": json.loads(GEOMETRY.read_text(encoding="utf-8"))["layouts"]["LAYOUT"]["layout"],
            "layers": [], "combos": [],
            "planned": [l[2:].strip() for l in PLANNED.read_text(encoding="utf-8").splitlines()
                        if l.startswith("- ")] if PLANNED.exists() else []}
    for name in LAYERS:
        keys = []
        for pos, b in enumerate(layers[name]):
            k = label(b)
            k["raw"] = b
            if name == "BASE" and b in BASE_SHIFTED:
                k["h"] = BASE_SHIFTED[b]
            twin = layers.get(name + " WIN", [None] * len(layers[name]))[pos]
            if b in ("&kp LG(LEFT)", "&kp LG(RIGHT)") and twin in BY_WIN_TWIN:
                k["t"] = BY_WIN_TWIN[twin]
            if b in ("&bootloader", "&sys_reset"):   # works on the half where it is pressed
                k["t"] += " L" if pos in LEFT else " R"
            keys.append(k)
        data["layers"].append({"name": name, "keys": keys})

    seen = set()
    for c in km["combos"]:
        on = [l for l in (c["layers"] or LAYERS) if l in LAYERS]
        if not on or tuple(c["positions"]) in seen:
            continue  # Windows-only copy of a Mac combo
        seen.add(tuple(c["positions"]))
        t = COMBO_NAME.get(c["binding"]) or label(c["binding"])["t"]
        data["combos"].append({"pos": c["positions"], "label": t, "layers": on})

    payload = json.dumps(data, ensure_ascii=False)
    stamp = hashlib.sha1(payload.encode()).hexdigest()[:10]
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__DATA__", payload.replace("</", "<\\/"))
    html = html.replace("__STAMP__", stamp).replace("__STAND__", stand())
    ideas = IDEAS.read_text(encoding="utf-8") if IDEAS.exists() else "Noch keine Ideen."
    html = html.replace("__IDEAS__", md_to_html(ideas))
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(data['layers'])} layers, {len(data['combos'])} combos)")


if __name__ == "__main__":
    main()
