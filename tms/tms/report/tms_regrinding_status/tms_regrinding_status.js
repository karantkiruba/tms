// Copyright (c) 2026, Spokes and contributors
// For license information, please see license.txt

frappe.query_reports["TMS Regrinding Status"] = {
	"filters": [
        {
            fieldname: "status",
            label: "Status",
            fieldtype: "Select",
            options: [
                "",
                "Pending Regrinding",
                "Completed",
                "Rejected"
            ].join("\n")
        },
        {
            fieldname: "near_max_only",
            label: "Only Tools Near Maximum Regrind",
            fieldtype: "Check",
            default: 0
        }
	]
};
