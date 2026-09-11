// Copyright (c) 2026, Spokes and contributors
// For license information, please see license.txt

frappe.query_reports["TMS Standard Versus Actual Tool Cost"] = {
	"filters": [
        {
            fieldname: "tool_type",
            label: __("TMS Tool Type"),
            fieldtype: "Link",
            options: "TMS Tool Type"
        },
        {
            fieldname: "regrindable_only",
            label: __("Regrindable Only"),
            fieldtype: "Check"
        },
        {
            fieldname: "variance_only",
            label: __("With Variance Only"),
            fieldtype: "Check"
        }
	]
};
