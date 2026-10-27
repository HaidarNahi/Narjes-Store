// Copyright (c) 2026, Narjes Custom and contributors
// For license information, please see license.txt

frappe.query_reports["Intake Phone Audit"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: "2026-08-01",
        },
        {
            fieldname: "hide_cancelled",
            label: __("Hide Cancelled Orders"),
            fieldtype: "Check",
            default: 1,
        },
    ],
};
