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
		 "options": "CPC Component", "width": 200},
		{"label": _("New Tools"), "fieldname": "new_qty", "fieldtype": "Float", "width": 100},
		{"label": _("New Tool Value"), "fieldname": "new_value", "fieldtype": "Currency",
		 "width": 140},
		{"label": _("Reground Tools"), "fieldname": "rg_qty", "fieldtype": "Float",
		 "width": 120},
		{"label": _("Reground Value"), "fieldname": "rg_value", "fieldtype": "Currency",
		 "width": 140},
		{"label": _("Other Tooling Qty"), "fieldname": "other_qty", "fieldtype": "Float",
		 "width": 130},
		{"label": _("Other Tooling Value"), "fieldname": "other_value", "fieldtype": "Currency",
		 "width": 150},
		{"label": _("Additional Value"), "fieldname": "additional_value", "fieldtype": "Currency",
		 "width": 140},
		{"label": _("Total Issue Value"), "fieldname": "total_value", "fieldtype": "Currency",
		 "width": 150},
	]


def get_data(filters):
	"""Section 33: value split by New, Reground and supporting tooling."""
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
		select issue.cpc_component, item.qty, item.issue_value, item.additional_qty,
		       item.valuation_rate,
		       coalesce(cond.is_regrind_output, 0) as is_reground,
		       coalesce(tt.is_regrindable, 0) as is_main_tool
		from `tabTMS Tool Issue Item` item
		inner join `tabTMS Tool Issue` issue on issue.name = item.parent
		left join `tabTMS Tool Condition` cond on cond.name = item.tool_condition
		left join `tabTMS Tool Type` tt on tt.name = item.tool_type
		where {conditions}
		""".format(conditions=" and ".join(conditions)),
		values, as_dict=True,
	)

	grouped = {}
	for row in rows:
		bucket = grouped.setdefault(row.cpc_component, {
			"cpc_component": row.cpc_component, "new_qty": 0, "new_value": 0,
			"rg_qty": 0, "rg_value": 0, "other_qty": 0, "other_value": 0,
			"additional_value": 0, "total_value": 0,
		})

		if not row.is_main_tool:
			# inserts, taps and supporting tooling are managed by quantity and value
			bucket["other_qty"] += flt(row.qty)
			bucket["other_value"] += flt(row.issue_value)
		elif row.is_reground:
			bucket["rg_qty"] += flt(row.qty)
			bucket["rg_value"] += flt(row.issue_value)
		else:
			bucket["new_qty"] += flt(row.qty)
			bucket["new_value"] += flt(row.issue_value)

		bucket["additional_value"] += flt(row.additional_qty) * flt(row.valuation_rate)
		bucket["total_value"] += flt(row.issue_value)

	return sorted(grouped.values(), key=lambda r: -r["total_value"])
