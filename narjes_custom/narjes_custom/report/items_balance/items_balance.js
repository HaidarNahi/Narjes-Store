// Copyright (c) 2026, Narjes Custom and contributors
// For license information, please see license.txt

frappe.query_reports["Items Balance"] = {
    filters: [],

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "balance" && data && data.is_low_balance) {
            value = `<span style="color: red; font-weight: bold;">${value}</span>`;
        }

        return value;
    }
};
