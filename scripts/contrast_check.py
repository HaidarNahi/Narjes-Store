#!/usr/bin/env python3
"""P12.1 — mechanical WCAG contrast matrix for every semantic pairing in
tokens.json, both modes. Writes docs/CONTRAST.md and exits non-zero if any
required pairing fails its threshold (AA: 4.5 body text, 3.0 large/UI).

Run from the app root:  python3 scripts/contrast_check.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "narjes_custom" / "public" / "tokens.json"
OUT = ROOT / "docs" / "CONTRAST.md"


def srgb(channel):
    channel /= 255
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def luminance(hexcolor):
    hexcolor = hexcolor.lstrip("#")
    r, g, b = (int(hexcolor[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b)


def ratio(fg, bg):
    l1, l2 = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def build_pairings(sem, ramps, singles, mode="light"):
    """(label, fg, bg, threshold) per mode — the promises P1.1 makes."""
    r = lambda name, stop: ramps[name][str(stop)]

    # Chart tooltips invert the page: a dark panel on the light theme, a light
    # panel on the dark one. That inversion is why they are listed explicitly
    # rather than derived from `sem` — the panel is never the page's surface,
    # so nothing in the semantic set describes it, and the one time it went
    # unchecked the value sat at 1.44:1 and the number was invisible.
    if mode == "light":
        tip_bg = singles["ink"]
        tip_value, tip_title, tip_label = r("neutral", 50), r("neutral", 300), r("neutral", 400)
    else:
        tip_bg = r("neutral", 200)
        tip_value, tip_title, tip_label = singles["ink"], r("neutral", 800), r("neutral", 700)

    return [
        ("body text on canvas", sem["text"], sem["bg"], 4.5),
        ("body text on surface", sem["text"], sem["surface"], 4.5),
        ("body text on raised", sem["text"], sem["raised"], 4.5),
        ("secondary text on canvas", sem["text-2"], sem["bg"], 4.5),
        ("secondary text on surface", sem["text-2"], sem["surface"], 4.5),
        ("tertiary text on surface (large/meta)", sem["text-3"], sem["surface"], 3.0),
        ("primary button label", sem["primary-text-on"], sem["primary"], 4.5),
        ("link on canvas", sem["link"], sem["bg"], 4.5),
        ("link on surface", sem["link"], sem["surface"], 4.5),
        ("accent text on accent tint", sem["accent-text"], sem["accent-bg"], 4.5),
        ("danger text on danger tint", sem["danger-text"], sem["danger-bg"], 4.5),
        ("success text on success tint", sem["success"], sem["success-bg"], 4.5),
        ("info text on info tint", sem["info"], sem["info-bg"], 4.5),
        ("focus ring on canvas (UI)", sem["focus"], sem["bg"], 3.0),
        ("border-strong on surface (UI)", sem["border-strong"], sem["surface"], 1.2),
        ("text on selection", sem["text"], sem["selection"], 4.5),
        ("chart tooltip value on panel", tip_value, tip_bg, 4.5),
        ("chart tooltip date on panel", tip_title, tip_bg, 4.5),
        ("chart tooltip label on panel", tip_label, tip_bg, 4.5),
        # The explainer button sits on the report summary strip, which is the
        # sunken ground rather than a card. 3.0 because it is a control, not body
        # text — and it shipped once at 2.1:1, which is why it is listed here.
        ("explainer button on summary strip", sem["text-2"], sem["sunken"], 3.0),
        ("explainer button hover", sem["primary"], sem["sunken"], 3.0),
    ]


def readable_on(bg):
    """Mirror of readable_on() in js/narjes/brand.js — the label color the
    runtime picks for text sitting on a given accent."""
    ink, paper = "#121714", "#FFFFFF"
    return ink if ratio(ink, bg) >= ratio(paper, bg) else paper


def accent_presets():
    """THEME_PRESETS from narjes_custom/api.py — the accents Narjes Settings →
    Appearance can apply at runtime. These override --n-primary, so they must
    be contrast-checked too: the static token pairing passing is not enough
    (the Ink-mode preset accents are light, the static dark token is dark)."""
    src = (ROOT / "narjes_custom" / "api.py").read_text()
    m = re.search(r"THEME_PRESETS\s*=\s*\{(.*?)\n\}", src, re.S)
    if not m:
        return {}
    presets, current = {}, None
    for line in m.group(1).splitlines():
        name = re.match(r'\s*"(\w+)":\s*\{\s*$', line)
        if name:
            current = name.group(1)
            presets[current] = {}
            continue
        mode = re.match(r'\s*"(light|dark)":\s*\{([^}]*)\}', line)
        if mode and current:
            presets[current][mode.group(1)] = dict(
                re.findall(r'"(\w+)":\s*"(#[0-9A-Fa-f]{6})"', mode.group(2))
            )
    return presets


tokens = json.loads(TOKENS.read_text())
LIGHT = tokens["semantic"]["light"]
DARK = tokens["semantic"]["dark"]

rows, failures = [], []
for mode, sem, mode_key in (("Paper (light)", LIGHT, "light"), ("Ink (dark)", DARK, "dark")):
    for label, fg, bg, threshold in build_pairings(sem, tokens["ramps"], tokens["singles"], mode_key):
        value = ratio(fg, bg)
        ok = value >= threshold
        if not ok:
            failures.append((mode, label, value, threshold))
        rows.append(
            f"| {mode} | {label} | `{fg}` on `{bg}` | {value:.2f} | {threshold} |"
            f" {'✅' if ok else '❌'} |"
        )

for preset, modes in accent_presets().items():
    for mode_key, canvas in (("light", LIGHT), ("dark", DARK)):
        accent = modes.get(mode_key, {}).get("fern")
        if not accent:
            continue
        mode = f"{preset} accent · {'Paper' if mode_key == 'light' else 'Ink'}"
        for label, fg, bg, threshold in (
            ("button label on accent", readable_on(accent), accent, 4.5),
            ("accent fill vs canvas (UI)", accent, canvas["bg"], 3.0),
        ):
            value = ratio(fg, bg)
            ok = value >= threshold
            if not ok:
                failures.append((mode, label, value, threshold))
            rows.append(
                f"| {mode} | {label} | `{fg}` on `{bg}` | {value:.2f} | {threshold} |"
                f" {'✅' if ok else '❌'} |"
            )

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(
    "# Narjes Ledger — contrast matrix (generated by scripts/contrast_check.py)\n\n"
    "WCAG AA: 4.5:1 body text, 3:1 large text / UI components.\n\n"
    "| Mode | Pairing | Colors | Ratio | Min | Pass |\n|---|---|---|---|---|---|\n"
    + "\n".join(rows)
    + "\n"
)
print(f"wrote {OUT} — {len(rows)} pairings, {len(failures)} failures")
for f in failures:
    print(f"  FAIL {f[0]} · {f[1]}: {f[2]:.2f} < {f[3]}")
sys.exit(1 if failures else 0)
