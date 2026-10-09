# Totem – Ideenspeicher

Ideen für die Keymap, die bewusst (noch) nicht umgesetzt sind. Bei Bedarf hier nachschlagen und dann im Totem-Planer vormerken.
Diese Datei ist die Quelle; der Planer zeigt sie im Reiter "Ideen".

## ß per Halten einer Buchstabentaste
*Notiert am 07.10.2026*

- **Idee:** Eine Buchstabentaste auf der Basis bekommt eine zweite Funktion beim Halten: antippen = Buchstabe, halten = ß.
- **Nicht auf `s`:** `s` ist schon Home-Row-Mod (Ctrl am Mac, Win unter Windows). Eine Taste kann beim Halten nur eine Sache tun.
- **Bester Kandidat: `z` halten = ß** (Position 22, linke Hand unten, Ringfinger). Gute Eselsbrücke ("sz"), bisher keine Halte-Funktion. `z` ist Teil der Kombos Undo (k+z) und Cut (z+'). Kombos und Halten vertragen sich in ZMK grundsätzlich, die Kombo wird zuerst ausgewertet. Testen.
- **Alternative: `ü` halten = ß** (Position 20, links unten außen, kleiner Finger). Keine Kombo, keine Halte-Funktion, aber ungünstige Position.
- **Kosten:** ß erscheint erst nach der Haltezeit (ca. 0,2 s). Wer beim langsamen Tippen auf der Taste liegen bleibt, bekommt ß statt des Buchstabens.
- **Heute:** ß über Sym halten + Position 19 (unter `s`). Das bliebe auch mit der neuen Lösung erhalten.
- **Technik in ZMK:** Hold-Tap mit `flavor = "tap-preferred"`, `tapping-term-ms` um 200, Bindings `<&kp>, <&kp>`, z. B. `&ht DE_SZ DE_Z` (Mac) bzw. `DEW_SZ DEW_Z` (Windows-Zwilling).
