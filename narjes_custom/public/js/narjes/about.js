// SHIM_REGISTRY.md #2 — About dialog: replaces frappe.ui.misc.about with a
// Narjes-branded box (plan P8.3). No framework credits in the user-facing
// dialog; version string comes from the narjes_custom app.

function narjes_about() {
	if (!frappe.ui.misc) frappe.ui.misc = {};
	frappe.ui.misc.about = function () {
		if (!frappe.ui.misc.about_dialog) {
			const version =
				(frappe.boot.versions && frappe.boot.versions.narjes_custom) || "1.0";
			const d = new frappe.ui.Dialog({ title: __("Narjes Store") });
			$(d.body).html(
				`<div style="text-align:center;padding:24px 8px;">
					<img src="/assets/narjes_custom/images/narjes-logo.svg"
						alt="Narjes" style="width:56px;height:56px;margin-bottom:12px;">
					<h4 style="font-family:var(--n-font-display);margin:0 0 4px;">
						${__("Narjes Store")}</h4>
					<p style="font-family:var(--n-font-mono);color:var(--n-text-3);margin:0;">
						v${version}</p>
					<p style="color:var(--n-text-2);margin-top:12px;">
						${__("Support")}: haimohx@gmail.com</p>
				</div>`
			);
			frappe.ui.misc.about_dialog = d;
		}
		frappe.ui.misc.about_dialog.show();
	};
}

$(document).on("app_ready", narjes_about);
