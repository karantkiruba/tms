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
		{"label": _("Billed Qty"), "fieldname": "billed_qty", "fieldtype": "Float",
		 "width": 110},
		{"label": _("CPC Billing Value"), "fieldname": "billing_value", "fieldtype": "Currency",
		 "width": 150},
		{"label": _("New Tool Value"), "fieldname": "new_value", "fieldtype": "Currency",
		 "width": 140},
		{"label": _("Reground Value"), "fieldname": "rg_value", "fieldtype": "Currency",
		 "width": 140},
		{"label": _("Other Tooling"), "fieldname": "other_value", "fieldtype": "Currency",
		 "width": 130},
		{"label": _("Total Tool Issue"), "fieldname": "tool_issue_value", "fieldtype": "Currency",
		 "width": 150},
		{"label": _("Tool Value / Component"), "fieldname": "value_per_component",
		 "fieldtype": "Currency", "precision": 4, "width": 170},
		{"label": _("Contribution"), "fieldname": "contribution", "fieldtype": "Currency",
		 "width": 150},
		{"label": _("Contribution %"), "fieldname": "contribution_pct", "fieldtype": "Percent",
		 "width": 130},
	]


def get_data(filters):
	"""Sections 37 and 38. An operational comparison, not accounting gross profit."""
	billing = get_billing(filters)
	issues = get_tool_issue(filters)

	components = sorted(set(billing) | set(issues))
	data = []
	for component in components:
		bill = billing.get(component, {})
		issue = issues.get(component, {})

		billing_value = flt(bill.get("billing_value"))
		billed_qty = flt(bill.get("billed_qty"))
		tool_value = flt(issue.get("new_value")) + flt(issue.get("rg_value")) \
			+ flt(issue.get("other_value"))

		data.append({
			"cpc_component": component,
			"billed_qty": billed_qty,
			"billing_value": billing_value,
			"new_value": flt(issue.get("new_value")),
			"rg_value": flt(issue.get("rg_value")),
			"other_value": flt(issue.get("other_value")),
			"tool_issue_value": tool_value,
			"value_per_component": (tool_value / billed_qty) if billed_qty else 0,
			"contribution": billing_value - tool_value,
			"contribution_pct": ((billing_value - tool_value) / billing_value * 100)
			if billing_value else 0,
		})

	return sorted(data, key=lambda r: -r["billing_value"])


def get_billing(filters):
	conditions = ["s.docstatus = 1", "s.from_date >= %(from_date)s", "s.to_date <= %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.tms_location:
		conditions.append("s.tms_location = %(tms_location)s")
		values["tms_location"] = filters.tms_location
	if filters.cpc_component:
		conditions.append("i.cpc_component = %(cpc_component)s")
		values["cpc_component"] = filters.cpc_component

	rows = frappe.db.sql(
		"""
		select i.cpc_component,
		       sum(i.current_billing_qty) as billed_qty,
		       sum(i.billing_value) as billing_value
		from `tabTMS CPC Billing Item` i
		inner join `tabTMS CPC Billing Statement` s on s.name = i.parent
		where {conditions}
		group by i.cpc_component
		""".format(conditions=" and ".join(conditions)),
		values, as_dict=True,
	)
	return {r.cpc_component: r for r in rows}


def get_tool_issue(filters):
	conditions = ["issue.docstatus = 1",
	              "issue.posting_date between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.tms_location:
		conditions.append("issue.tms_location = %(tms_location)s")
		values["tms_location"] = filters.tms_location
	if filters.cpc_component:
		conditions.append("issue.cpc_component = %(cpc_component)s")
		values["cpc_component"] = filters.cpc_component

	rows = frappe.db.sql(
		"""
		select issue.cpc_component, item.issue_value,
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
		bucket = grouped.setdefault(row.cpc_component,
		                            {"new_value": 0, "rg_value": 0, "other_value": 0})
		if not row.is_main_tool:
			bucket["other_value"] += flt(row.issue_value)
		elif row.is_reground:
			bucket["rg_value"] += flt(row.issue_value)
		else:
			bucket["new_value"] += flt(row.issue_value)
	return grouped
