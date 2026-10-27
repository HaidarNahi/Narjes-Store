// Copyright (c) 2026, Narjes Custom and contributors
// For license information, please see license.txt

frappe.query_reports["Customer Phone Check"] = {
    filters: [
        {
            fieldname: "problem",
            label: __("Problem"),
            fieldtype: "Select",
            options: "\nShared with another customer\nInvalid phone\nMain = secondary\nNo phone",
        },
    ],
};
