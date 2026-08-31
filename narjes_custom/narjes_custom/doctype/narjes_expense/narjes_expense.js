// Narjes Expense — form behaviour.
//
// Two jobs: keep the account pickers honest, and offer the "write a sentence,
// get a filled form" shortcut. The parse only ever FILLS FIELDS — it never
// saves and never submits, so nothing reaches the ledger without someone
// reading it first.

frappe.ui.form.on("Narjes Expense", {
    setup(frm) {
        // Category: expense heads only. Without this the picker offers every
        // account on the chart, including income and group accounts, and the
        // server-side check in validate() becomes the first time anyone finds
        // out they picked wrong.
        frm.set_query("expense_account", () => ({
            filters: {
                root_type: "Expense",
                is_group: 0,
                company: frm.doc.company,
            },
        }));

        // Paid From: only somewhere money can actually leave.
        frm.set_query("paid_from", () => ({
            filters: {
                account_type: ["in", ["Cash", "Bank"]],
                is_group: 0,
                company: frm.doc.company,
            },
        }));

        frm.set_query("cost_center", () => ({
            filters: { is_group: 0, company: frm.doc.company },
        }));
    },

    onload(frm) {
        if (frm.is_new()) {
            if (!frm.doc.company) {
                frm.set_value("company", frappe.defaults.get_user_default("Company"));
            }
            if (!frm.doc.expense_date) {
                frm.set_value("expense_date", frappe.datetime.get_today());
            }
            if (!frm.doc.paid_from && frm.doc.company) {
                frappe.db.get_value("Company", frm.doc.company, "default_cash_account")
                    .then((r) => {
                        if (r.message && r.message.default_cash_account) {
                            frm.set_value("paid_from", r.message.default_cash_account);
                        }
                    });
            }
        }
    },

    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Read This"), () => parse_raw_text(frm)).addClass(
                "btn-primary"
            );
        }

        if (frm.doc.docstatus === 1 && frm.doc.journal_entry) {
            frm.add_custom_button(__("Journal Entry"), () => {
                frappe.set_route("Form", "Journal Entry", frm.doc.journal_entry);
            });
        }
    },
});

function parse_raw_text(frm) {
    const text = (frm.doc.raw_text || "").trim();
    if (!text) {
        frappe.msgprint({
            title: __("Nothing to read"),
            message: __("Write what you spent in the box above first."),
            indicator: "orange",
        });
        return;
    }

    frappe.dom.freeze(__("Reading..."));
    frappe.call({
        method: "narjes_custom.expenses.api.parse_expense",
        args: { raw_text: text, company: frm.doc.company },
        callback: (r) => {
            frappe.dom.unfreeze();
            const res = r.message;
            if (!res || !res.ok) {
                frappe.msgprint({
                    title: __("Could not read that"),
                    message: (res && res.error) || __("Try writing it a different way."),
                    indicator: "red",
                });
                return;
            }

            const f = res.fields;
            // Only fill what came back. A blank from the parser means "not
            // sure" — overwriting something the operator already typed with
            // an empty value would be actively unhelpful.
            if (f.description) frm.set_value("description", f.description);
            if (f.payee) frm.set_value("payee", f.payee);
            if (f.amount) frm.set_value("amount", f.amount);
            if (f.expense_account) frm.set_value("expense_account", f.expense_account);
            if (f.expense_date) frm.set_value("expense_date", f.expense_date);
            if (f.notes) frm.set_value("notes", f.notes);

            if (res.warnings && res.warnings.length) {
                frappe.msgprint({
                    title: __("Check these"),
                    message: res.warnings.map((w) => `<li>${frappe.utils.escape_html(w)}</li>`).join(""),
                    indicator: "orange",
                });
            } else {
                frappe.show_alert({
                    message: __("Filled in — check it, then save."),
                    indicator: "green",
                });
            }
        },
        error: () => frappe.dom.unfreeze(),
    });
}
