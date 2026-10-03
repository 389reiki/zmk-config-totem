#!/usr/bin/env python3
"""Writes docs/keycodes.md: every character with the name to use in config/totem.keymap.

Run from the repo root:  python tools/make_keycode_list.py
Only needed again if config/keys_de_mac.h or config/keys_de_win.h change.
"""
import re
from collections import OrderedDict

from keymap_lib import MAC_H, ROOT, WIN_H


def names_by_char(path, prefix):
    """character -> [names] in header order (first = full name, then short aliases)."""
    out = OrderedDict()
    cur = None
    for line in path.read_text(encoding="utf-8").splitlines():
        c = re.match(r"/\* (.+) \*/\s*$", line)
        if c:
            cur = c.group(1)
            continue
        d = re.match(rf"#define ({prefix}_\w+) ", line)
        if d and cur:
            out.setdefault(cur, []).append(d.group(1))
    return out


def main():
    mac = names_by_char(MAC_H, "DE")
    win = names_by_char(WIN_H, "DEW")

    def esc(ch):
        return {"|": "\\|", "`": "`` ` ``"}.get(ch, ch)

    lines = [
        "# Key names for config/totem.keymap",
        "",
        "Search this page (Cmd+F) for the character you want. Use the **Mac name** in the macOS layers",
        "and the **Windows name** in the matching `..._win_layer` (see *HOW TO EDIT* at the top of the keymap).",
        "Write it as `&kp NAME`, e.g. `&kp DE_SECT`. Shorter names work too; on Windows they start",
        "with `DEW_` instead of `DE_` (`DE_SECT` -> `DEW_SECT`).",
        "",
        "Generated from `config/keys_de_mac.h` and `config/keys_de_win.h` by `tools/make_keycode_list.py`.",
        "",
        "| Character | Mac name | Windows name | Shorter names (same key) |",
        "|---|---|---|---|",
    ]
    order = list(mac) + [c for c in win if c not in mac]
    skip = {"DE_SPACE"}
    for ch in order:
        m = [n for n in mac.get(ch, []) if n not in skip]
        w = win.get(ch, [])
        if not m and not w:
            continue
        mac_name = f"`{m[0]}`" if m else "– (not on the Mac layout)"
        win_name = f"`{w[0]}`" if w else "– (not on the Windows layout)"
        aliases = ", ".join(f"`{n}`" for n in m[1:]) if m else ", ".join(f"`{n}`" for n in w[1:])
        lines.append(f"| {esc(ch)} | {mac_name} | {win_name} | {aliases} |")
    lines += [
        "",
        "Special keys (same on both systems): `BSPC` Backspace, `DEL` Delete, `RET` Enter, `TAB`, `ESC`,",
        "`SPACE`, `LEFT` `RIGHT` `UP` `DOWN`, `HOME` `END` `PG_UP` `PG_DN`, `F1`…`F24`.",
        "Full list: https://zmk.dev/docs/keymaps/list-of-keycodes",
        "",
    ]
    out = ROOT / "docs" / "keycodes.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(order)} characters)")


if __name__ == "__main__":
    main()
