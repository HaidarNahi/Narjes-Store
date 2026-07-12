// Override the Customer Quick Entry to hide
// "Primary Contact Details" and "Primary Address Details" sections.
// We keep only the doctype's own quick-entry fields (customer_name, etc.)

frappe.ui.form.CustomerQuickEntryForm = class CustomerQuickEntryForm extends (
    frappe.ui.form.QuickEntryForm
) {
    constructor(doctype, after_insert, init_callback, doc, force) {
        super(doctype, after_insert, init_callback, doc, force);
        this.skip_redirect_on_error = true;
    }

    // Return empty array — no contact/address sections
    get_variant_fields() {
        return [];
    }

    render_dialog() {
        this.mandatory = this.mandatory.concat(this.get_variant_fields());
        super.render_dialog();
    }
};
