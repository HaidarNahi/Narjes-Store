// purchase_order.js — Narjes Custom: Transportation Charges auto-sync
// When the user types a transportation cost, this JS automatically
// adds/updates/removes the corresponding row in the Taxes and Charges table.

frappe.ui.form.on("Purchase Order", {
    transportation_charges: function (frm) {
        sync_transportation_tax_row(frm);
    },

    onload: function (frm) {
        // On load, if the taxes table already has a transportation row,
        // populate the transportation_charges field from it
        if (frm.is_new()) return;

        const row = find_transportation_row(frm);
        if (row && row.tax_amount) {
            frm.set_value("transportation_charges", row.tax_amount);
        }
    },
});

function find_transportation_row(frm) {
    return (frm.doc.taxes || []).find(
        (t) =>
            t.account_head === "Transportation Charges - NS" &&
            t.description === "Transportation Charges"
    );
}

function sync_transportation_tax_row(frm) {
    const amount = flt(frm.doc.transportation_charges);
    const existing = find_transportation_row(frm);

    if (amount > 0) {
        if (existing) {
            // Update existing row
            frappe.model.set_value(existing.doctype, existing.name, "tax_amount", amount);
        } else {
            // Add new row
            const row = frm.add_child("taxes", {
                charge_type: "Actual",
                account_head: "Transportation Charges - NS",
                description: "Transportation Charges",
                category: "Valuation and Total",
                add_deduct_tax: "Add",
                tax_amount: amount,
            });
        }
    } else {
        // Amount is 0 or empty — remove the transportation row if it exists
        if (existing) {
            frm.doc.taxes = frm.doc.taxes.filter(
                (t) => t.name !== existing.name
            );
        }
    }

    frm.refresh_field("taxes");
    frm.trigger("calculate_taxes_and_totals");
}
