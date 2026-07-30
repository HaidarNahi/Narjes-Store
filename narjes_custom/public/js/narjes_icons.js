// Renders icons from Narjes Custom's own Phosphor sprite
// (narjes_custom/public/icons/phosphor/icons.svg, loaded app-wide via the
// `app_include_icons` hook). Symbol ids are namespaced `ph-*` so they never
// collide with Frappe/ERPNext's own icon sprite ids. All icons use
// fill="currentColor" internally, so color is controlled entirely by CSS
// (color / --icon-fill-bg) on the element or an ancestor.
function narjes_icon(name, opts) {
	opts = opts || {};
	var size = opts.size || "sm";
	var extra_class = opts.class || "";
	var size_style = "";
	if (typeof size === "object") {
		size_style = ` style="width:${size.width};height:${size.height}"`;
	}
	var size_class = typeof size === "string" ? `icon-${size}` : "";
	return (
		`<svg class="icon narjes-icon ${size_class} ${extra_class}"${size_style} aria-hidden="true">` +
		`<use href="#ph-${name}"></use>` +
		`</svg>`
	);
}
