// Narjes Ledger boot: kill-switch body class, theme-switcher relabel,
// awesomebar placeholder, terminal-state stamps. Desk only.

const TERMINAL_STATUSES = new Set([
	"completed", "done", "paid", "submitted", "cancelled", "returned", "closed",
	"مكتمل", "ملغي",
]);

function apply_body_class() {
	const enabled = !frappe.boot || frappe.boot.narjes_theme_enabled !== false;
	document.body.classList.toggle("narjes-ledger", enabled);
}

// The pre-theme fixed "Home" button duplicated the breadcrumb home icon
// (issue #4). Its injector was deleted from customer_quick_entry.js, but that
// file is served un-versioned and lives in browser caches — actively remove
// the button so stale caches can't resurrect it. Drop this a few releases in.
function remove_legacy_home_button() {
	const kill = () => document.getElementById("narjes-navbar-home-btn")?.remove();
	kill();
	// the old injector ran on a 1s timeout — sweep after it would have fired
	setTimeout(kill, 1500);
	setTimeout(kill, 3500);
}

// SHIM_REGISTRY.md #1 — Theme switcher labels: "Frappe Light" → "Paper",
// "Timeless Night" → "Ink" (plan P3.4). Skins the native mechanism; does not
// fork it. Verified against v16.20 theme_switcher.js.
function relabel_theme_switcher() {
	if (!frappe.ui || !frappe.ui.ThemeSwitcher) return;
	const original = frappe.ui.ThemeSwitcher.prototype.fetch_themes;
	frappe.ui.ThemeSwitcher.prototype.fetch_themes = function () {
		return original.call(this).then((themes) => {
			const labels = { light: __("Paper"), dark: __("Ink"), automatic: __("Auto") };
			(this.themes || themes || []).forEach((t) => {
				if (labels[t.name]) t.label = labels[t.name];
			});
			return this.themes;
		});
	};
}

// SHIM_REGISTRY.md #3 — Awesomebar placeholder: "Search orders, customers…"
// instead of the stock text. DOM-level; re-applied on page change because the
// navbar search input can re-render.
function set_search_placeholder() {
	const input = document.querySelector("#navbar-search");
	if (input) input.setAttribute("placeholder", __("Search orders, customers…"));
}

// (The workspace-sidebar brand — module icon + "ERPNext" app name — used to be
// a JS shim here. Frappe re-renders that header after page-change, so any JS
// swap loses the race; it's now handled race-free in _chrome.scss. See
// SHIM_REGISTRY.md.)

// Terminal states get the stamped variant on the page-head indicator
// (plan P1.6/P5.4) — never applied in lists en masse.
function stamp_terminal_indicator() {
	document.querySelectorAll(".page-head .indicator-pill").forEach((pill) => {
		const label = (pill.textContent || "").trim().toLowerCase();
		pill.classList.toggle("n-stamp--stamped", TERMINAL_STATUSES.has(label));
	});
}

$(document).on("app_ready", () => {
	apply_body_class();
	relabel_theme_switcher();
	set_search_placeholder();
	remove_legacy_home_button();
});

$(document).on("page-change", () => {
	set_search_placeholder();
	// let the route render its header first
	setTimeout(stamp_terminal_indicator, 300);
});

// also catch the initial load
if (document.readyState !== "loading") {
	apply_body_class();
} else {
	document.addEventListener("DOMContentLoaded", apply_body_class);
}
