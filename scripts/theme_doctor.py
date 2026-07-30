#!/usr/bin/env python3
"""P13.4 — theme doctor. Asserts the theme's load-bearing pieces survived a
build / bench update: bundles built and mapped, kill-switch scope present,
Lever-1 remaps present, sprite present, key selectors compiled in, size
budgets respected. Run after every `bench update` (see UPGRADE_NOTES.md).

Run from the app root:  python3 scripts/theme_doctor.py
"""

import gzip
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
BENCH = APP.parent.parent
DIST = APP / "narjes_custom" / "public" / "dist"
ASSETS_JSON = BENCH / "sites" / "assets" / "assets.json"

BUDGET_CSS_GZ = 90 * 1024
BUDGET_JS_GZ = 25 * 1024
BUDGET_FONTS = 380 * 1024

failures = []


def check(label, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(label)


print("narjes theme doctor\n")

# 1. bundles registered in assets.json
assets = json.loads(ASSETS_JSON.read_text()) if ASSETS_JSON.exists() else {}
css_key = assets.get("narjes.bundle.css", "")
js_key = assets.get("narjes.bundle.js", "")
check("desk css bundle mapped", bool(css_key), css_key)
check("desk js bundle mapped", bool(js_key), js_key)
check("web css bundle mapped", bool(assets.get("narjes-web.bundle.css")))

# 2. built css contains the load-bearing pieces
css_path = BENCH / "sites" / css_key.lstrip("/").replace("assets/", "assets/", 1)
css_path = BENCH / "sites" / "assets" / css_key.split("/assets/")[-1] if css_key else None
if css_path and not css_path.exists():
    css_path = DIST / "css" / Path(css_key).name
css = css_path.read_text() if css_path and css_path.exists() else ""
check("built css found", bool(css), str(css_path))
for probe, why in [
    ("body.narjes-ledger", "kill-switch scope"),
    ("--green-500:var(--n-fern-500)", "Lever-1 ramp remap (light)"),
    ("[data-theme=dark] body.narjes-ledger", "Lever-1 dark map"),
    ("--font-stack:var(--n-font-body)", "brand font stack"),
    (".so-kanban-card", "kanban card skin"),
    ("Fraunces", "display face"),
]:
    check(f"css contains {why}", probe.replace(" ", "") in css.replace(" ", ""))

# 3. sprite + logo + patterns
for rel, label in [
    ("icons/phosphor/icons.svg", "phosphor sprite"),
    ("images/narjes-logo.svg", "logo"),
    ("images/favicon.svg", "favicon"),
    ("patterns/vine-light.svg", "vine light"),
    ("patterns/vine-dark.svg", "vine dark"),
    ("patterns/grain.svg", "grain"),
]:
    check(f"asset {label}", (APP / "narjes_custom" / "public" / rel).exists())

# 4. budgets
if css:
    gz = len(gzip.compress(css.encode()))
    check("css budget ≤ 90 KB gz", gz <= BUDGET_CSS_GZ, f"{gz / 1024:.1f} KB")
js_path = DIST / "js" / Path(js_key).name if js_key else None
if js_path and js_path.exists():
    gz = len(gzip.compress(js_path.read_bytes()))
    check("js budget ≤ 25 KB gz", gz <= BUDGET_JS_GZ, f"{gz / 1024:.1f} KB")
fonts_total = sum(
    f.stat().st_size for f in (APP / "narjes_custom" / "public" / "fonts").glob("*.woff2")
)
check("fonts budget ≤ 380 KB", fonts_total <= BUDGET_FONTS, f"{fonts_total / 1024:.0f} KB")

print()
if failures:
    print(f"{len(failures)} check(s) failed")
    sys.exit(1)
print("all checks green")
