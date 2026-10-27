frappe.listview_settings["AI Order Intake"] = {
	add_fields: ["status", "match_status"],
	get_indicator(doc) {
		const colors = {
			"Needs Review": "orange",
			Confirmed: "green",
			Failed: "red",
			Discarded: "gray",
			Draft: "gray",
		};
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
