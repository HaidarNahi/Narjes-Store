#!/usr/bin/env python3
"""Generate _tokens.scss + narjes-vars.css from public/tokens.json.

The JSON is the single source of truth (plan P1); the two outputs are build
artifacts committed alongside it so `bench build` needs no extra tooling.

Run from the app root:  python3 scripts/generate_tokens.py
"""

import json
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "narjes_custom"
TOKENS = APP / "public" / "tokens.json"
OUT_SCSS = APP / "public" / "scss" / "narjes" / "_tokens.scss"
OUT_CSS = APP / "public" / "css" / "narjes-vars.css"

HEADER = (
    "/* GENERATED from public/tokens.json by scripts/generate_tokens.py — "
    "DO NOT HAND-EDIT. */\n\n"
)


def emit_block(selector, pairs, indent="\t"):
    lines = [f"{selector} {{"]
    for name, value in pairs:
        lines.append(f"{indent}{name}: {value};")
    lines.append("}\n")
    return "\n".join(lines)


def build():
    tokens = json.loads(TOKENS.read_text())

    light, dark = [], []

    for ramp, stops in tokens["ramps"].items():
        for stop, hexval in stops.items():
            light.append((f"--n-{ramp}-{stop}", hexval))
    for name, hexval in tokens["singles"].items():
        light.append((f"--n-{name}", hexval))

    for key, val in tokens["semantic"]["light"].items():
        light.append((f"--n-{key}", val))
    for key, val in tokens["semantic"]["dark"].items():
        dark.append((f"--n-{key}", val))

    t = tokens["type"]
    light.append(("--n-font-display", t["font-display"]))
    light.append(("--n-font-body", t["font-body"]))
    light.append(("--n-font-mono", t["font-mono"]))

    for k, v in tokens["space"].items():
        light.append((f"--n-space-{k}", v))
    for k, v in tokens["radius"].items():
        light.append((f"--n-radius-{k}", v))
    for k, v in tokens["shadow"]["light"].items():
        light.append((f"--n-{k}", v))
    for k, v in tokens["shadow"]["dark"].items():
        dark.append((f"--n-{k}", v))
    for k, v in tokens["z"].items():
        light.append((f"--n-z-{k}", v))
    for k, v in tokens["motion"].items():
        light.append((f"--n-{k}", v))

    css = HEADER
    css += emit_block(':root,\n[data-theme="light"]', light)
    css += "\n"
    css += emit_block('[data-theme="dark"]', dark)

    # Type-role helper classes ride along in the same generated file so the
    # scale in tokens.json is the only place sizes are written.
    roles = []
    fam = {"display": "--n-font-display", "body": "--n-font-body", "mono": "--n-font-mono"}
    for role, spec in t["scale"].items():
        rules = [
            f"\tfont-family: var({fam[spec['family']]});",
            f"\tfont-size: {spec['size']};",
            f"\tline-height: {spec['line']};",
            f"\tfont-weight: {spec['weight']};",
        ]
        if spec["family"] == "mono":
            rules.append('\tfont-variant-numeric: tabular-nums;')
            rules.append('\tfont-feature-settings: "tnum";')
        if spec.get("transform"):
            rules.append(f"\ttext-transform: {spec['transform']};")
        if spec.get("tracking"):
            rules.append(f"\tletter-spacing: {spec['tracking']};")
        roles.append(".n-type-%s {\n%s\n}\n" % (role, "\n".join(rules)))
    css += "\n" + "".join(roles)

    OUT_SCSS.parent.mkdir(parents=True, exist_ok=True)
    OUT_CSS.parent.mkdir(parents=True, exist_ok=True)
    OUT_SCSS.write_text(css)
    OUT_CSS.write_text(css)
    print(f"wrote {OUT_SCSS.relative_to(APP.parent)} and {OUT_CSS.relative_to(APP.parent)}")


if __name__ == "__main__":
    build()
