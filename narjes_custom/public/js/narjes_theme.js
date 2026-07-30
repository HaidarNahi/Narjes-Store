// Single source of truth for brand color values needed as raw JS strings
// (frappe.Chart series colors, hand-built SVG/markup) — mirrors the
// --narjes-* tokens declared in narjes_custom/public/css/theme/tokens.css.
var NARJES_BRAND = {
	paper: "#F2F4F1",
	paperRaised: "#FFFFFF",
	paperSunken: "#E9EDE7",

	ink: "#1B211D",
	inkMuted: "#5B655C",
	inkFaint: "#8B948A",

	border: "#DCE3DA",
	borderStrong: "#C3CDC0",

	fern: "#2E5C46",
	fernStrong: "#234433",
	fernTint: "#E4F0EA",

	sage: "#A2D4C9",

	saffron: "#C8842A",
	saffronTint: "#F7EAD6",
	saffronText: "#8A5A17",

	stamp: "#9B3B3B",
	stampTint: "#F5E4E2",

	success: "#2E5C46",
	warning: "#8A5A17",
	danger: "#9B3B3B",
	neutral: "#8B948A",
};

// Live accent reconfiguration — Narjes Settings > Appearance lets an admin
// pick a preset (or a fully custom accent) without a bench build or asset
// rebuild: extend_bootinfo() resolves the chosen accent server-side into
// light+dark {fern, strong, tint} triples and ships them as
// frappe.boot.narjes_theme; this just patches the 3 CSS custom properties
// that everything else (buttons, links, sidebar selection, indicator
// pills — all wired through frappe_overrides.css) already reads from.
// Same mechanism the approved theme-preview artifact demonstrated live.
(function () {
	function apply_narjes_theme() {
		var theme = frappe.boot && frappe.boot.narjes_theme;
		if (!theme || !theme.light || !theme.dark) return;

		var root = document.documentElement;
		root.style.setProperty("--narjes-fern", theme.light.fern);
		root.style.setProperty("--narjes-fern-strong", theme.light.strong);
		root.style.setProperty("--narjes-fern-tint", theme.light.tint);

		var style_id = "narjes-accent-override";
		var style_tag = document.getElementById(style_id);
		if (!style_tag) {
			style_tag = document.createElement("style");
			style_tag.id = style_id;
			document.head.appendChild(style_tag);
		}
		style_tag.textContent =
			':root[data-theme="dark"] {' +
			"--narjes-fern:" + theme.dark.fern + ";" +
			"--narjes-fern-strong:" + theme.dark.strong + ";" +
			"--narjes-fern-tint:" + theme.dark.tint + ";" +
			"}" +
			"@media (prefers-color-scheme: dark) {" +
			':root:not([data-theme="light"]) {' +
			"--narjes-fern:" + theme.dark.fern + ";" +
			"--narjes-fern-strong:" + theme.dark.strong + ";" +
			"--narjes-fern-tint:" + theme.dark.tint + ";" +
			"}}";

		NARJES_BRAND.fern = theme.light.fern;
		NARJES_BRAND.fernStrong = theme.light.strong;
		NARJES_BRAND.fernTint = theme.light.tint;
		NARJES_BRAND.success = theme.light.fern;
	}

	if (frappe.boot) {
		apply_narjes_theme();
	} else {
		$(document).on("frappe.ready", apply_narjes_theme);
	}
})();
