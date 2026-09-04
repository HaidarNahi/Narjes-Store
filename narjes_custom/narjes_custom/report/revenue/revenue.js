// Copyright (c) 2026, Narjes Custom and contributors
// For license information, please see license.txt

/* global frappe, __ */

frappe.query_reports["Revenue"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
		},
		{
			fieldname: "compare",
			label: __("Compare with the period before"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
	],

	formatter(value, row, column, data, default_formatter) {
		const out = default_formatter(value, row, column, data);
		const kind = data && data.kind;

		// The three totals are the spine of the report; the accounts under
		// them are supporting detail. Weight says which is which faster than
		// reading does.
		if (column.fieldname === "step") {
			if (kind === "net") return `<b style="font-size:1.05em">${out}</b>`;
			if (kind === "total") return `<b>${out}</b>`;
			if (kind === "correction") return `<span style="color:var(--text-muted)">${out}</span>`;
			return `<span style="color:var(--text-muted)">${out}</span>`;
		}

		if (column.fieldname === "amount") {
			const styled = `font-variant-numeric:tabular-nums;`;
			if (kind === "net") {
				const tone = value >= 0 ? "var(--green-600)" : "var(--red-600)";
				return `<b style="${styled}color:${tone};font-size:1.05em">${out}</b>`;
			}
			if (kind === "correction") {
				return `<span style="${styled}color:var(--text-muted)">${out}</span>`;
			}
			if (kind === "total") return `<b style="${styled}">${out}</b>`;
			const tone = value < 0 ? "var(--red-600)" : "inherit";
			return `<span style="${styled}color:${tone}">${out}</span>`;
		}

		if (column.fieldname === "change" && value) {
			const tone = value >= 0 ? "var(--green-600)" : "var(--red-600)";
			const arrow = value >= 0 ? "↑" : "↓";
			return `<span style="font-variant-numeric:tabular-nums;color:${tone}">${arrow} ${out}</span>`;
		}

		return out;
	},
};
