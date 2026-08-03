// Copyright (c) 2026, Narjes Custom and contributors
// For license information, please see license.txt

const PROMPT_FIELDS = [
	"system_prompt_base",
	"extraction_rules",
	"extra_instructions",
	"few_shot_examples",
];

frappe.ui.form.on("AI Intake Settings", {
	refresh(frm) {
		enable_word_wrap(frm);
		show_disabled_headline(frm);

		frm.add_custom_button(__("Test Connection"), () => with_saved(frm, test_connection));
		frm.add_custom_button(__("Preview System Prompt"), () => with_saved(frm, preview_prompt));
		frm.add_custom_button(__("Restore Default Prompts"), () => restore_default_prompts(frm));
	},

	enabled(frm) {
		show_disabled_headline(frm);
	},
});

// Prompts are long prose, not code — without wrapping, every line runs off
// the right edge of the editor. `wrap` isn't a DocField property, so it can
// only be set on the Ace instance, which is built asynchronously.
function enable_word_wrap(frm, tries = 0) {
	let pending = false;

	PROMPT_FIELDS.forEach((fieldname) => {
		const control = frm.fields_dict[fieldname];
		if (!control) return;
		if (control.editor) {
			control.editor.setOption("wrap", true);
		} else {
			pending = true;
		}
	});

	if (pending && tries < 10) {
		setTimeout(() => enable_word_wrap(frm, tries + 1), 200);
	}
}

function show_disabled_headline(frm) {
	if (frm.doc.enabled) {
		frm.dashboard.clear_headline();
		return;
	}
	frm.dashboard.set_headline(
		__("AI Order Intake is turned off — the intake page will refuse new text."),
		"orange"
	);
}

// Every action reads the saved document, so unsaved edits would be
// invisible to it. Save first rather than previewing a stale prompt.
function with_saved(frm, action) {
	if (frm.is_dirty()) {
		frm.save().then(() => action(frm));
	} else {
		action(frm);
	}
}

function preview_prompt(frm) {
	frappe.call({
		method:
			"narjes_custom.narjes_custom.doctype.ai_intake_settings.ai_intake_settings.preview_system_prompt",
		freeze: true,
		freeze_message: __("Assembling prompt…"),
		callback(r) {
			if (!r.message) return;
			const d = r.message;
			const dialog = new frappe.ui.Dialog({
				title: __("System Prompt Preview"),
				size: "large",
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "stats",
						options: `<p style="color: var(--text-muted); font-size: 12px;">
							${format_number(d.characters)} ${__("characters")} ·
							~${format_number(d.approx_tokens)} ${__("tokens")} ·
							${d.catalog_items} ${__("catalog items")} ·
							${d.examples} ${__("examples")}
						</p>`,
					},
					{
						fieldtype: "Code",
						fieldname: "prompt",
						label: __("Sent as the system instruction"),
						read_only: 1,
						default: d.prompt,
					},
				],
				primary_action_label: __("Close"),
				primary_action: () => dialog.hide(),
			});
			dialog.show();
			setTimeout(() => {
				const editor = dialog.fields_dict.prompt.editor;
				if (editor) editor.setOption("wrap", true);
			}, 300);
		},
	});
}

function test_connection(frm) {
	frappe.call({
		method:
			"narjes_custom.narjes_custom.doctype.ai_intake_settings.ai_intake_settings.test_connection",
		freeze: true,
		freeze_message: __("Sending a sample order to the model…"),
		callback(r) {
			if (!r.message) return;
			const d = r.message;

			if (!d.ok) {
				frappe.msgprint({
					title: __("Connection failed"),
					indicator: "red",
					message: `<p>${frappe.utils.escape_html(d.error)}</p>${
						d.model
							? `<p style="color: var(--text-muted); font-size: 12px;">${__("Model")}:
								${frappe.utils.escape_html(d.model)} · ${__("Key from")}:
								${frappe.utils.escape_html(d.key_source || "—")}</p>`
							: ""
					}`,
				});
				return;
			}

			frappe.msgprint({
				title: __("Connection OK"),
				indicator: "green",
				message: `
					<p>${__("The model extracted a sample order in {0}s.", [d.elapsed])}</p>
					<p style="color: var(--text-muted); font-size: 12px;">
						${__("Model")}: ${frappe.utils.escape_html(d.model)} ·
						${__("Key from")}: ${frappe.utils.escape_html(d.key_source)}
					</p>
					<pre style="max-height: 320px; overflow: auto; font-size: 12px;">${frappe.utils.escape_html(
						d.extracted
					)}</pre>`,
			});
		},
	});
}

function restore_default_prompts(frm) {
	frappe.confirm(
		__(
			"Replace the System Prompt Base and Extraction Rules with the shipped defaults? Your current text will be lost."
		),
		() => {
			const meta = frappe.get_meta(frm.doctype);
			["system_prompt_base", "extraction_rules"].forEach((fieldname) => {
				const df = meta.fields.find((f) => f.fieldname === fieldname);
				if (df) frm.set_value(fieldname, df.default);
			});
			frappe.show_alert({
				message: __("Default prompts restored — save to apply."),
				indicator: "blue",
			});
		}
	);
}
