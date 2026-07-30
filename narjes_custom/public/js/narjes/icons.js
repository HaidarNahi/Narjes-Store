// narjes_icon() — renders from the app's Phosphor sprite (ph-* symbol ids,
// loaded app-wide via app_include_icons). Window global because page scripts
// call it unqualified. Absorbed from the pre-theme narjes_icons.js.

window.narjes_icon = function (name, opts) {
	opts = opts || {};
	const size = opts.size || "sm";
	const extra_class = opts.class || "";
	let size_style = "";
	if (typeof size === "object") {
		size_style = ` style="width:${size.width};height:${size.height}"`;
	}
	const size_class = typeof size === "string" ? `icon-${size}` : "";
	return (
		`<svg class="icon narjes-icon ${size_class} ${extra_class}"${size_style} aria-hidden="true">` +
		`<use href="#ph-${name}"></use>` +
		`</svg>`
	);
};
