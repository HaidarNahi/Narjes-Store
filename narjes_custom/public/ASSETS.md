# Brand asset index (theme plan P2)

| Asset | Path | Usage rules |
|---|---|---|
| Logo (brand colors) | `images/narjes-logo.svg` | Navbar, About, letterhead, /apps card. Mint mark as shipped. |
| Mark (currentColor) | `images/narjes-mark.svg` | Inline-able; recolor via CSS: fern-600 on Paper, mint on Ink, white on fern. Clear space = one petal width. |
| Favicon | `images/favicon.svg` | Fern on light tabs, mint on dark (`prefers-color-scheme` inside the SVG). |
| Splash | `images/splash.svg` | Boot splash via `website_context`. Wordmark uses serif fallback (SVG-in-img can't load webfonts). |
| Vine pattern | `patterns/vine-{light,dark}.svg` | Full-opacity strokes; strength set per surface via CSS `opacity`. Placement is FIXED (P1.5): login, splash, modal header, dropzone, empty states, print watermark, email band. Nowhere else. |
| Grain | `patterns/grain.svg` | App canvas, light mode only, 2% baked. |
| Fonts | `fonts/*.woff2` | Self-hosted OFL; latin (Fraunces, Plex Sans/Mono) + arabic (Plex Sans Arabic, Amiri 400). 313 KB total, budget 380. Regenerate via `scripts/fetch_fonts.py`. |
| Phosphor sprite | `icons/phosphor/icons.svg` | Additive `ph-*` symbol ids via `app_include_icons`; render with `narjes_icon()`. Weights: regular default, fill for active states. |

Pending (produce when needed): 8-piece empty-state illustration set, email
header band PNG @2x, OG/share image 1200×630, A5 letterhead art variant.
