#!/usr/bin/env python3
"""Generate the storefront's brand assets from the narcissus mark (plan W1).

Outputs into public/images/storefront/ and public/patterns/:
  placeholder-product.svg  shared stand-in for un-photographed items
  pattern-lattice.svg      petal-arc lattice (section dividers)
  pattern-bloom.svg        sparse bloom scatter (hero / empty states)

Run from the app root:  python3 scripts/build_storefront_assets.py
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "narjes_custom"
MARK = APP / "public" / "images" / "narjes-mark.svg"
IMG_OUT = APP / "public" / "images" / "storefront"
PAT_OUT = APP / "public" / "patterns"

MINT = "#A2D4C9"
FERN = "#2E5C46"
PAPER = "#F7F8F6"

# One petal of the mark, reused for the generated patterns.
PETAL = "M0 0 C -5 -10, -2 -20, 0 -26 C 2 -20, 5 -10, 0 0 Z"


def mark_inner():
    """The three narcissus paths, stripped of their <svg> wrapper."""
    svg = MARK.read_text()
    inner = re.sub(r"^<svg[^>]*>|</svg>\s*$", "", svg.strip())
    return re.sub(r'\s*fill="currentColor"', "", inner)


def placeholder():
    """Square product stand-in: the mark on a mint→paper wash.

    Deliberately understated — it appears on every un-photographed item, so it
    must read as a considered brand surface rather than a 'missing image' icon
    (plan W4.1).
    """
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800" role="img" aria-label="Narjes">
  <defs>
    <linearGradient id="wash" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{MINT}" stop-opacity="0.30"/>
      <stop offset="55%" stop-color="{MINT}" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="{PAPER}" stop-opacity="1"/>
    </linearGradient>
    <g id="ph-petal" fill="none" stroke="{FERN}" stroke-width="1.4" stroke-linecap="round">
      <path d="{PETAL}"/>
      <path d="{PETAL}" transform="rotate(120)"/>
      <path d="{PETAL}" transform="rotate(-120)"/>
    </g>
  </defs>
  <rect width="800" height="800" fill="{PAPER}"/>
  <rect width="800" height="800" fill="url(#wash)"/>
  <g opacity="0.10">
    <use href="#ph-petal" transform="translate(120 140) rotate(18) scale(1.6)"/>
    <use href="#ph-petal" transform="translate(680 210) rotate(-24) scale(1.2)"/>
    <use href="#ph-petal" transform="translate(150 660) rotate(40) scale(1.3)"/>
    <use href="#ph-petal" transform="translate(660 640) rotate(-8) scale(1.7)"/>
  </g>
  <g transform="translate(400 400) scale(0.14) translate(-780 -757)" fill="{MINT}" opacity="0.85">
    {mark_inner()}
  </g>
</svg>
"""


def lattice():
    """Interlocking petal arcs — quiet enough to sit behind content."""
    arcs = []
    for row in range(-1, 4):
        for col in range(-1, 4):
            x, y = col * 120, row * 120
            arcs.append(
                f'<path d="M {x} {y + 60} C {x + 30} {y}, {x + 90} {y}, {x + 120} {y + 60}"/>'
            )
            arcs.append(
                f'<path d="M {x} {y + 60} C {x + 30} {y + 120}, {x + 90} {y + 120}, {x + 120} {y + 60}"/>'
            )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="360" viewBox="0 0 360 360">
  <!-- Petal-arc lattice. Full-opacity strokes; per-surface strength set in CSS. -->
  <g fill="none" stroke="{FERN}" stroke-width="1" stroke-linecap="round">
    {chr(10).join("    " + a for a in arcs)}
  </g>
</svg>
"""


def bloom():
    """Sparse three-petal blooms for hero and empty states."""
    spots = [
        (90, 110, 0, 1.5), (300, 80, 35, 1.0), (200, 250, -20, 1.8),
        (400, 330, 15, 1.2), (110, 400, -40, 1.1), (330, 460, 25, 1.6),
    ]
    uses = "\n".join(
        f'    <use href="#bloom-unit" transform="translate({x} {y}) rotate({r}) scale({s})"/>'
        for x, y, r, s in spots
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="520" height="520" viewBox="0 0 520 520">
  <!-- Sparse narcissus blooms. Full-opacity strokes; strength set in CSS. -->
  <defs>
    <g id="bloom-unit" fill="none" stroke="{FERN}" stroke-width="1.2" stroke-linecap="round">
      <path d="{PETAL}"/>
      <path d="{PETAL}" transform="rotate(120)"/>
      <path d="{PETAL}" transform="rotate(-120)"/>
      <circle cx="0" cy="0" r="2.5"/>
    </g>
  </defs>
{uses}
</svg>
"""


def main():
    IMG_OUT.mkdir(parents=True, exist_ok=True)
    PAT_OUT.mkdir(parents=True, exist_ok=True)
    written = [
        (IMG_OUT / "placeholder-product.svg", placeholder()),
        (PAT_OUT / "pattern-lattice.svg", lattice()),
        (PAT_OUT / "pattern-bloom.svg", bloom()),
    ]
    for path, content in written:
        path.write_text(content)
        print(f"  {path.relative_to(APP.parent)}  {len(content) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
