// Supplier Contacts grid: keep the four columns of the child table always
// visible, at the widths defined on the Supplier Contacts doctype
// (Name 2 · Position 1 · Main Phone Number 2 · Secondary Phone Number 2).
//
// Frappe's "Configure Columns" writes a per-user override into User Settings
// (Supplier > GridView > "Supplier Contacts"), and grid.setup_user_defined_columns()
// applies that override INSTEAD of the doctype's own in_list_view/columns.
// One user having reconfigured the grid once is enough for them to keep seeing
// a different set of columns forever. Clearing the override on load makes the
// doctype definition the single source of truth, which is what "fixed" means
// here — change the columns in the child doctype, not per user.

const NARJES_SUPPLIER_CONTACTS = 'Supplier Contacts';

frappe.ui.form.on('Supplier', {
	refresh: function (frm) {
		enforce_contacts_grid_columns(frm);
	},
});

function enforce_contacts_grid_columns(frm) {
	const grid_field = Object.values(frm.fields_dict || {}).find(
		(f) => f.df && f.df.fieldtype === 'Table' && f.df.options === NARJES_SUPPLIER_CONTACTS
	);
	if (!grid_field || !grid_field.grid) return;

	const settings = frappe.get_user_settings(frm.doctype, 'GridView') || {};
	const has_override =
		settings[NARJES_SUPPLIER_CONTACTS] && settings[NARJES_SUPPLIER_CONTACTS].length;

	const grid = grid_field.grid;

	if (has_override) {
		// Drop only this grid's override; leave any other grid on the form alone.
		const cleaned = Object.assign({}, settings);
		delete cleaned[NARJES_SUPPLIER_CONTACTS];
		frappe.model.user_settings
			.save(frm.doctype, 'GridView', Object.keys(cleaned).length ? cleaned : null)
			.then(() => {
				grid.user_defined_columns = null;
				grid.visible_columns = null;
				grid.setup_visible_columns && grid.setup_visible_columns();
				grid.refresh();
			});
		return;
	}

	// No override stored — just make sure the grid is showing the doctype's
	// own columns (it may have been rendered before this ran).
	if (grid.user_defined_columns && grid.user_defined_columns.length) {
		grid.user_defined_columns = null;
		grid.visible_columns = null;
		grid.setup_visible_columns && grid.setup_visible_columns();
		grid.refresh();
	}
}
