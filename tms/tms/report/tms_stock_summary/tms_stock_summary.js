// Copyright (c) 2026, Spokes and contributors
// For license information, please see license.txt

frappe.query_reports["TMS Stock Summary"] = {
	"filters": [
        {
            fieldname: "tool_type",
            label: __("Tool Type"),
            fieldtype: "Link",
            options: "TMS Tool Type"
        },
        {
            fieldname: "hide_zero",
            label: __("Hide Zero Stock"),
            fieldtype: "Check"
        }
	]
};
