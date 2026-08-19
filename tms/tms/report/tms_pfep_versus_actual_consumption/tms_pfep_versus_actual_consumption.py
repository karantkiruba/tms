# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("CPC Component"), "fieldname": "cpc_component", "fieldtype": "Link",
		 "options": "CPC Component", "width": 190},
		{"label": _("Tool Type"), "fieldname": "tool_type", "fieldtype": "Link",
		 "options": "TMS Tool Type", "width": 160},
		{"label": _("Machine"), "fieldname": "machine", "fieldtype": "Link",
		 "options": "TMS Customer Machine", "width": 150},
		{"label": _("PFEP Standard"), "fieldname": "pfep_qty", "fieldtype": "Float",
		 "width": 130},
		{"label": _("Actual Issued"), "fieldname": "actual_qty", "fieldtype": "Float",
		 "width": 130},
		{"label": _("Variance"), "fieldname": "variance", "fieldtype": "Float", "width": 110},
		{"label": _("Variance %"), "fieldname": "variance_pct", "fieldtype": "Percent",
		 "width": 110},
		{"label": _("Issue Value"), "fieldname": "issue_value", "fieldtype": "Currency",
		 "width": 140},
	]


def get_data(filters):
	"""Section 39: actual issue against the PFEP standard for the same period."""
	conditions = ["issue.docstatus = 1", "issue.posting_date between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.tms_location:
		conditions.append("issue.tms_location = %(tms_location)s")
		values["tms_location"] = filters.tms_location
	if filters.cpc_component:
		conditions.append("issue.cpc_component = %(cpc_component)s")
		values["cpc_component"] = filters.cpc_component

	rows = frappe.db.sql(
		"""
		select issue.cpc_component, issue.machine, item.tool_type,
		       sum(item.pfep_standard_qty) as pfep_qty,
		       sum(item.qty) as actual_qty,
		       sum(item.issue_value) as issue_value
		from `tabTMS Tool Issue Item` item
		inner join `tabTMS Tool Issue` issue on issue.name = item.parent
		where {conditions}
		group by issue.cpc_component, issue.machine, item.tool_type
		order by issue.cpc_component, item.tool_type
		""".format(conditions=" and ".join(conditions)),
		values, as_dict=True,
	)

	for row in rows:
		row.variance = flt(row.actual_qty) - flt(row.pfep_qty)
		row.variance_pct = (row.variance / flt(row.pfep_qty) * 100) if flt(row.pfep_qty) else 0
	return rows
