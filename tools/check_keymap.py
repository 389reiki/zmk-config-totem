#!/usr/bin/env python3
"""Checks that every macOS key and its Windows twin do the same job.

Run from the repo root:  python tools/check_keymap.py      (no extra packages needed)
The GitHub build runs this first and stops if it finds a mismatch.

How it compares a Mac key with the same position in its Windows twin layer:
  - Keycodes are compared by the character they type (DE_AT on Mac and DEW_AT on Windows both type @).
  - &trans in the Windows twin means "same as the Mac key". That is fine unless the Mac key sends a
    Mac-only keystroke (Cmd, Mac Ctrl, a *_mac macro, or a symbol that sits on a different key on Mac).
  - Shortcuts: Cmd+X on Mac is expected to be Ctrl+X on Windows, and the bare modifiers swap
    (Mac Cmd = Windows Ctrl, Mac Ctrl = Windows Win, Option = Alt).
  - Everything else must be identical, unless it is listed in EQUIVALENT below.

If you add a key that is deliberately different on Windows, add the pair to EQUIVALENT.
Write keycodes as the character in ⟨ ⟩ (e.g. ⟨z⟩) the way this script prints them.
"""
import re
import sys

from keymap_lib import N_KEYS, MAC_H, WIN_H, describe, read_header, read_keymap

# Mac binding -> allowed Windows bindings (same job, different keystroke)
EQUIVALENT = {
    "&kp LA(LEFT)": {"&kp LC(LEFT)"},                    # word left
    "&kp LA(RIGHT)": {"&kp LC(RIGHT)"},                  # word right
    "&kp LG(LEFT)": {"&kp HOME", "&kp LA(LEFT)"},        # line start / browser back
    "&kp LG(RIGHT)": {"&kp END", "&kp LA(RIGHT)"},       # line end / browser forward
    "&kp LG(TAB)": {"&kp LA(TAB)"},                      # switch app
    "&kp LA(BSPC)": {"&kp LC(BSPC)"},                    # delete word
    "&kp LG(LS(⟨5⟩))": {"&kp PSCRN"},                    # screenshot
    "&kp LG(LS(⟨z⟩))": {"&kp LC(⟨y⟩)", "&kp LC(LS(⟨z⟩))"},  # redo
    "&gif_mac": {"&gif_win"},
    "&tilde_mac": {"&kp ⟨~⟩"},
    "&bsw LA(BSPC) 0": {"&bsw LC(BSPC) 0"},              # Backspace key, hold = delete word
    "&swapper_mac": {"&swapper_win"},                    # Cmd-Tab / Alt-Tab swapper
    "&kp LG(⟨[⟩)": {"&kp LA(LEFT)"},                    # back (mouse layer)
    "&kp LG(⟨]⟩)": {"&kp LA(RIGHT)"},                   # forward (mouse layer)
}
# Keys that do the same on both systems even though their name ends in _mac
NEUTRAL = {"&host_mac", "&host_win", "&smart_mouse"}
SWAP_MODS = {"LGUI": "LCTRL", "LCTRL": "LGUI", "RGUI": "RCTRL", "RCTRL": "RGUI"}


def main():
    km = read_keymap()
    mac_def, mac_chr = read_header(MAC_H)
    win_def, win_chr = read_header(WIN_H)

    def norm(binding):
        """Replace DE_x / DEW_x keycodes by the character they type."""
        def sub(m):
            name = m.group(0)
            ch = (win_chr if name.startswith("DEW_") else mac_chr).get(name)
            return f"⟨{ch}⟩" if ch else name
        return re.sub(r"\bDEW?_\w+", sub, binding)

    def same_keystroke_on_both(name):
        """DE_x sends the same key on Mac as DEW_x on Windows (letters, digits, most punctuation)."""
        w = "DEW_" + name[3:]
        return w in win_def and mac_def.get(name, "").replace("DE_", "") == win_def[w].replace("DEW_", "")

    def mac_only(binding):
        if binding in NEUTRAL:
            return False
        if re.search(r"\bLG\(|\bLGUI\b|\bLCTRL\b|\bRGUI\b|\bRCTRL\b|_mac\b", binding):
            return True
        return any(not same_keystroke_on_both(n) for n in re.findall(r"\bDE_\w+", binding))

    def expected(mac_b):
        n = norm(mac_b)
        if n in EQUIVALENT:
            return EQUIVALENT[n]
        swapped = " ".join(SWAP_MODS.get(t, t) for t in n.split(" "))
        swapped = swapped.replace("LG(", "LC(")
        return {swapped}

    layers = {l[1]: l[2] for l in km["layers"]}
    errors = []

    for name, keys in layers.items():
        if len(keys) != N_KEYS:
            errors.append(f"Layer {name}: has {len(keys)} keys, needs {N_KEYS}.")
    if errors:
        return report(errors)

    pairs = [("BASE", "WIN")] + [(n, n + " WIN") for n in layers if not n.endswith("WIN") and n != "BASE"]
    for mac, win in pairs:
        if win not in layers:
            errors.append(f"Layer {mac} has no Windows twin '{win}'.")
            continue
        for pos, (m, w) in enumerate(zip(layers[mac], layers[win])):
            if w == "&trans":
                if mac_only(m):
                    errors.append(f"{mac} / {win}, {describe(pos)}: Mac sends {norm(m)}, but the Windows "
                                  f"twin is &trans, so Windows gets the Mac keystroke. Put the Windows "
                                  f"version there (allowed: {' or '.join(sorted(expected(m)))}).")
                continue
            if norm(w) not in expected(m):
                errors.append(f"{mac} / {win}, {describe(pos)}: Mac {norm(m)}  vs  Windows {norm(w)}. "
                              f"Expected on Windows: {' or '.join(sorted(expected(m)))}.")

    # combos: every Mac-only combo needs a Windows combo on the same keys, and vice versa
    win_layer_names = {n for n in layers if n.endswith("WIN")}
    mac_combos = [c for c in km["combos"] if c["layers"] and not set(c["layers"]) & win_layer_names]
    win_combos = [c for c in km["combos"] if c["layers"] and set(c["layers"]) <= win_layer_names]
    for c in mac_combos:
        twin = [w for w in win_combos if sorted(w["positions"]) == sorted(c["positions"])]
        if not twin:
            errors.append(f"Combo {c['name']} (keys {c['positions']}) has no Windows twin on the same keys.")
        elif norm(twin[0]["binding"]) not in expected(c["binding"]):
            errors.append(f"Combo {c['name']} / {twin[0]['name']}: Mac {norm(c['binding'])}  vs  Windows "
                          f"{norm(twin[0]['binding'])}. Expected: {' or '.join(sorted(expected(c['binding'])))}.")
    for w in win_combos:
        if not any(sorted(c["positions"]) == sorted(w["positions"]) for c in mac_combos):
            errors.append(f"Combo {w['name']} (keys {w['positions']}) has no Mac twin on the same keys.")

    return report(errors)


def report(errors):
    if errors:
        print("Mac and Windows versions of the keymap don't match:\n")
        for e in errors:
            print("  - " + e)
        print("\nFix config/totem.keymap (see 'HOW TO EDIT' at its top), or, if the difference is "
              "intended, add it to EQUIVALENT in tools/check_keymap.py.")
        return 1
    print("OK: every Mac key and its Windows twin do the same job.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
