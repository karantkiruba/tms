// Copyright (c) 2026, Spokes and contributors
// For license information, please see license.txt

frappe.query_reports["TMS Component Wise Tool Issue"] = {
	"filters": [
{
    fieldname: "from_date",
    label: __("From Date"),
    fieldtype: "Date",
    reqd: 1,
    default: frappe.datetime.month_start()
},
{
    fieldname: "to_date",
    label: __("To Date"),
    fieldtype: "Date",
    reqd: 1,
    default: frappe.datetime.get_today()
}, 
{
            fieldname: "cpc_component",
            label: __("CPC Component"),
            fieldtype: "Link",
            options: "CPC Component"
        },
        {
            fieldname: "Group By",
            label: __("group_by"),
            fieldtype: "Select",
            options: [
                "CPC Component",
                "Machine",
                "Operation",
		"Tool Type",
		"Condition"
            ]
        }
	]
};
