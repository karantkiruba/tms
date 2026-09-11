// Copyright (c) 2026, Spokes and contributors
// For license information, please see license.txt

frappe.query_reports["TMS Stock Coverage and Reorder"] = {
	"filters": [
        {
            fieldname: "cpc_component",
            label: __("CPC Component"),
            fieldtype: "Link",
            options: "CPC Component"
        },
        {
            fieldname: "monthly_production_plan",
            label: __("Monthly Production Plan"),
            fieldtype: "Float"
        },
        {
            fieldname: "working_days",
            label: __("Working Days per Month"),
            fieldtype: "Int",
	    default:"26"
        },
        {
            fieldname: "shortages_only",
            label: __("Shortages Only"),
            fieldtype: "Check"
        },
{
    fieldname: "source_warehouse",
    label: __("Source Warehouse"),
    fieldtype: "Link",
    options: "Warehouse",
    reqd: 1
},
{
    fieldname: "target_warehouse",
    label: __("Target Warehouse"),
    fieldtype: "Link",
    options: "Warehouse",
    reqd: 1
}
	]
};
