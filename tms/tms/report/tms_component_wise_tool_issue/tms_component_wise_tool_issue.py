# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


GROUP_FIELDS = {
	"CPC Component": ("issue.cpc_component", "CPC Component", "Link", "CPC Component"),
	"Machine": ("issue.machine", "Machine", "Link", "TMS Customer Machine"),
	"Operation": ("issue.operation", "Operation", "Link", "TMS Operation"),
	"Tool Type": ("item.tool_type", "Tool Type", "Link", "TMS Tool Type"),
	"Condition": ("item.tool_condition", "Condition", "Link", "TMS Tool Condition"),
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group = filters.group_by or "CPC Component"
	field, label, fieldtype, options = GROUP_FIELDS[group]
	return get_columns(label, fieldtype, options), get_data(filters, field)


def get_columns(label, fieldtype, options):
	return [
		{"label": _(label), "fieldname": "group_value", "fieldtype": fieldtype,
		 "options": options, "width": 200},
		{"label": _("Issues"), "fieldname": "issue_count", "fieldtype": "Int", "width": 90},
		{"label": _("Qty Issued"), "fieldname": "total_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Standard Qty"), "fieldname": "pfep_qty", "fieldtype": "Float",
		 "width": 120},
		{"label": _("Additional Qty"), "fieldname": "additional_qty", "fieldtype": "Float",
		 "width": 120},
		{"label": _("Issue Value"), "fieldname": "issue_value", "fieldtype": "Currency",
		 "width": 140},
	]


def get_data(filters, field):
	conditions = ["issue.docstatus = 1", "issue.posting_date between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.tms_location:
		conditions.append("issue.tms_location = %(tms_location)s")
		values["tms_location"] = filters.tms_location
	if filters.cpc_component:
		conditions.append("issue.cpc_component = %(cpc_component)s")
		values["cpc_component"] = filters.cpc_component

	return frappe.db.sql(
		"""
		select {field} as group_value,
		       count(distinct issue.name) as issue_count,
		       sum(item.qty) as total_qty,
		       sum(item.pfep_standard_qty) as pfep_qty,
		       sum(item.additional_qty) as additional_qty,
		       sum(item.issue_value) as issue_value
		from `tabTMS Tool Issue Item` item
		inner join `tabTMS Tool Issue` issue on issue.name = item.parent
		where {conditions}
		group by {field}
		order by issue_value desc
		""".format(field=field, conditions=" and ".join(conditions)),
		values, as_dict=True,
	)
