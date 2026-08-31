// Brand values as raw JS strings (charts, hand-built SVG) + the live accent
// mechanism (Narjes Settings → Appearance → frappe.boot.narjes_theme).
// Absorbed from the pre-theme narjes_theme.js; exported on window because
// page scripts (narjes_home.js, ai_intake.js) reference the global.

window.NARJES_BRAND = {
	paper: "#F2F4F1",
	paperRaised: "#FFFFFF",
	paperSunken: "#E7EAE6",

	ink: "#1B211D",
	inkMuted: "#4C544E",
	inkFaint: "#6A736C",

	border: "#E7EAE6",
	borderStrong: "#D7DCD7",

	fern: "#2E5C46",
	fernStrong: "#264C3A",
	fernTint: "#D8E6DE",
	fernSoft: "#5E8F77",

	sage: "#A2D4C9",
	mint: "#A2D4C9",

	saffron: "#C8842A",
	saffronTint: "#F4E1C4",
	saffronText: "#875618",

	stamp: "#9B3B3B",
	stampTint: "#EFD8D8",

	success: "#2E5C46",
	warning: "#875618",
	danger: "#9B3B3B",
	neutral: "#6A736C",

	// frappe-charts default series order (plan P6.8)
	chartPalette: ["#2E5C46", "#C8842A", "#8B948D", "#9B3B3B", "#A2D4C9", "#8DB6A2"],
};

// Live accent reconfiguration without a bench build: patches BOTH the legacy
// --narjes-* aliases and the new --n-primary tokens the theme reads.
// Label color for text sitting ON the accent. Must be computed, not fixed:
// the Ink-mode accents the presets ship are LIGHT (Fern #7FD4AE, Plum #DE9FC7,
// Teal #6FCBD1, Ochre #E0A44C) — the opposite polarity from the light-mode
// accents — and the "Custom" preset accepts any hex. A static value gave
// near-white labels on light mint in Ink mode: 1.52:1, unreadable.
function readable_on(bg) {
	const luminance = (hex) => {
		const h = hex.replace("#", "");
		const [r, g, b] = [0, 2, 4].map((i) => {
			const c = parseInt(h.slice(i, i + 2), 16) / 255;
			return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
		});
		return 0.2126 * r + 0.7152 * g + 0.0722 * b;
	};
	const contrast = (a, b) => {
		const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
		return (hi + 0.05) / (lo + 0.05);
	};
	const INK = "#121714";
	const PAPER = "#FFFFFF";
	return contrast(INK, bg) >= contrast(PAPER, bg) ? INK : PAPER;
}

function apply_narjes_accent() {
	const theme = frappe.boot && frappe.boot.narjes_theme;
	if (!theme || !theme.light || !theme.dark) return;

	// Both modes go into ONE injected stylesheet, and nothing is written as an
	// inline style on <html>. Inline custom properties on the root element beat
	// every stylesheet rule — including `:root[data-theme="dark"]` — so setting
	// the light accent inline (as the pre-theme version did) left Ink mode
	// permanently on the light accent. In a stylesheet the normal cascade
	// applies: `:root[data-theme="dark"]` (0,2,0) outranks `:root` (0,1,0).
	const block = (sel, v, tint_stop) =>
		`${sel} {` +
		`--narjes-fern:${v.fern};` +
		`--narjes-fern-strong:${v.strong};` +
		`--narjes-fern-tint:${v.tint};` +
		`--n-primary:${v.fern};` +
		`--n-primary-hover:${v.strong};` +
		`--n-primary-text-on:${readable_on(v.fern)};` +
		`--n-fern-${tint_stop}:${v.tint};` +
		`--n-selection:${v.tint};` +
		`}`;

	const style_id = "narjes-accent-override";
	let tag = document.getElementById(style_id);
	if (!tag) {
		tag = document.createElement("style");
		tag.id = style_id;
		document.head.appendChild(tag);
	}
	tag.textContent =
		block(':root, :root[data-theme="light"]', theme.light, 100) +
		block(':root[data-theme="dark"]', theme.dark, 800) +
		"@media (prefers-color-scheme: dark) {" +
		block(':root:not([data-theme="light"])', theme.dark, 800) +
		"}";

	window.NARJES_BRAND.fern = theme.light.fern;
	window.NARJES_BRAND.fernStrong = theme.light.strong;
	window.NARJES_BRAND.fernTint = theme.light.tint;
	window.NARJES_BRAND.success = theme.light.fern;
	window.NARJES_BRAND.chartPalette[0] = theme.light.fern;
}

// Desk type scale (Narjes Settings → Appearance → Font Size).
//
// Rewrites Frappe's own --text-* ramp rather than zooming the page. `zoom`
// was the tempting one-liner, but it scales the coordinate space too, which
// silently breaks anything positioning itself from getBoundingClientRect —
// the kanban assignee popover among them. Scaling the type tokens changes
// only type, so every layout calculation stays honest.
//
// The ramp is Frappe's (espresso/_typography.scss); --n-* type sizes ride
// along through the same multiplier so the custom kanban card scales with
// everything else.
const NARJES_TEXT_STEPS = {
	"--text-tiny": 11, "--text-2xs": 12, "--text-xs": 12, "--text-sm": 13,
	"--text-md": 14, "--text-base": 14, "--text-lg": 16, "--text-xl": 18,
	"--text-2xl": 20, "--text-3xl": 24, "--text-4xl": 26, "--text-5xl": 28,
	"--text-6xl": 32, "--text-7xl": 40, "--text-8xl": 44, "--text-9xl": 48,
};

function apply_narjes_font_scale() {
	const settings = (frappe.boot && frappe.boot.narjes_settings) || {};
	const scale = Number(settings.font_scale) || 1;

	const style_id = "narjes-font-scale";
	let tag = document.getElementById(style_id);

	if (scale === 1) {
		if (tag) tag.remove();
		document.documentElement.style.removeProperty("--n-font-scale");
		return;
	}

	if (!tag) {
		tag = document.createElement("style");
		tag.id = style_id;
		document.head.appendChild(tag);
	}

	const steps = Object.entries(NARJES_TEXT_STEPS)
		.map(([name, px]) => `${name}:${Math.round(px * scale * 100) / 100}px;`)
		.join("");

	tag.textContent =
		`:root{${steps}--n-font-scale:${scale};}` +
		// Frappe's desk sets an explicit base size on body; keep it in step so
		// anything inheriting rather than using a token scales too.
		`body{font-size:${Math.round(14 * scale * 100) / 100}px;}`;
}

function apply_narjes_appearance() {
	apply_narjes_accent();
	apply_narjes_font_scale();
}

if (window.frappe && frappe.boot) {
	apply_narjes_appearance();
} else {
	$(document).on("app_ready", apply_narjes_appearance);
}
