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
function apply_narjes_accent() {
	const theme = frappe.boot && frappe.boot.narjes_theme;
	if (!theme || !theme.light || !theme.dark) return;

	const root = document.documentElement;
	const set = (name, value) => root.style.setProperty(name, value);
	set("--narjes-fern", theme.light.fern);
	set("--narjes-fern-strong", theme.light.strong);
	set("--narjes-fern-tint", theme.light.tint);
	set("--n-primary", theme.light.fern);
	set("--n-primary-hover", theme.light.strong);
	set("--n-fern-100", theme.light.tint);
	set("--n-selection", theme.light.tint);

	const dark_block = (sel) =>
		`${sel} {` +
		`--narjes-fern:${theme.dark.fern};` +
		`--narjes-fern-strong:${theme.dark.strong};` +
		`--narjes-fern-tint:${theme.dark.tint};` +
		`--n-primary:${theme.dark.fern};` +
		`--n-primary-hover:${theme.dark.strong};` +
		`--n-fern-800:${theme.dark.tint};` +
		`--n-selection:${theme.dark.tint};` +
		`}`;

	const style_id = "narjes-accent-override";
	let tag = document.getElementById(style_id);
	if (!tag) {
		tag = document.createElement("style");
		tag.id = style_id;
		document.head.appendChild(tag);
	}
	tag.textContent =
		dark_block(':root[data-theme="dark"]') +
		"@media (prefers-color-scheme: dark) {" +
		dark_block(':root:not([data-theme="light"])') +
		"}";

	window.NARJES_BRAND.fern = theme.light.fern;
	window.NARJES_BRAND.fernStrong = theme.light.strong;
	window.NARJES_BRAND.fernTint = theme.light.tint;
	window.NARJES_BRAND.success = theme.light.fern;
	window.NARJES_BRAND.chartPalette[0] = theme.light.fern;
}

if (window.frappe && frappe.boot) {
	apply_narjes_accent();
} else {
	$(document).on("app_ready", apply_narjes_accent);
}
