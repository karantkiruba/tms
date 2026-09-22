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
		{
			"label": _("CPC Component"),
			"fieldname": "cpc_component",
			"fieldtype": "Link",
			"options": "CPC Component",
			"width": 200
		},
		{
			"label": _("New Tools"),
			"fieldname": "new_qty",
			"fieldtype": "Float",
			"width": 100
		},
		{
			"label": _("New Tool Value"),
			"fieldname": "new_value",
			"fieldtype": "Currency",
			"width": 140
		},
		{
			"label": _("Reground Tools"),
			"fieldname": "rg_qty",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": _("Reground Value"),
			"fieldname": "rg_value",
			"fieldtype": "Currency",
			"width": 140
		},
		{
			"label": _("Other Tooling Qty"),
			"fieldname": "other_qty",
			"fieldtype": "Float",
			"width": 130
		},
		{
			"label": _("Other Tooling Value"),
			"fieldname": "other_value",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"label": _("Additional Value"),
			"fieldname": "additional_value",
			"fieldtype": "Currency",
			"width": 140
		},
		{
			"label": _("Total Issue Value"),
			"fieldname": "total_value",
			"fieldtype": "Currency",
			"width": 150
		},
	]


def get_data(filters):
	"""
	TMS Monthly Tool Issue Statement

	Classification:
		Condition = New
			-> New Tools

		Condition = Regrinding Finished
			-> Reground Tools

		All other conditions
			-> Other Tooling

	Additional Value:
		additional_qty * valuation_rate

	Total Issue Value:
		Sum of issue_value
	"""

	conditions = [
		"issue.docstatus = 1",
		"issue.posting_date between %(from_date)s and %(to_date)s"
	]

	values = {
		"from_date": filters.from_date,
		"to_date": filters.to_date
	}

	# TMS Location filter
	if filters.tms_location:
		conditions.append(
			"issue.tms_location = %(tms_location)s"
		)
		values["tms_location"] = filters.tms_location

	# CPC Component filter
	if filters.cpc_component:
		conditions.append(
			"issue.cpc_component = %(cpc_component)s"
		)
		values["cpc_component"] = filters.cpc_component

	rows = frappe.db.sql(
		"""
		SELECT
			issue.cpc_component,
			item.qty,
			item.issue_value,
			item.additional_qty,
			item.valuation_rate,
			cond.condition_name AS condition_name

		FROM `tabTMS Tool Issue Item` item

		INNER JOIN `tabTMS Tool Issue` issue
			ON issue.name = item.parent

		LEFT JOIN `tabTMS Tool Condition` cond
			ON cond.name = item.tool_condition

		WHERE {conditions}
		""".format(
			conditions=" AND ".join(conditions)
		),
		values,
		as_dict=True,
	)

	grouped = {}

	for row in rows:

		# Create CPC Component bucket
		bucket = grouped.setdefault(
			row.cpc_component,
			{
				"cpc_component": row.cpc_component,

				"new_qty": 0,
				"new_value": 0,

				"rg_qty": 0,
				"rg_value": 0,

				"other_qty": 0,
				"other_value": 0,

				"additional_value": 0,

				"total_value": 0,
			}
		)

		# ---------------------------------------------------------
		# 1. NEW TOOL
		# ---------------------------------------------------------
		if row.condition_name == "New":

			bucket["new_qty"] += flt(row.qty)

			bucket["new_value"] += flt(row.issue_value)

		# ---------------------------------------------------------
		# 2. REGROUND TOOL
		# ---------------------------------------------------------
		elif row.condition_name == "Regrinding Finished":

			bucket["rg_qty"] += flt(row.qty)

			bucket["rg_value"] += flt(row.issue_value)

		# ---------------------------------------------------------
		# 3. OTHER TOOLING
		# ---------------------------------------------------------
		else:

			bucket["other_qty"] += flt(row.qty)

			bucket["other_value"] += flt(row.issue_value)

		# ---------------------------------------------------------
		# 4. ADDITIONAL VALUE
		# ---------------------------------------------------------
		bucket["additional_value"] += (
			flt(row.additional_qty)
			* flt(row.valuation_rate)
		)

		# ---------------------------------------------------------
		# 5. TOTAL ISSUE VALUE
		# ---------------------------------------------------------
		bucket["total_value"] += flt(row.issue_value)

	# Sort by Total Issue Value descending
	return sorted(
		grouped.values(),
		key=lambda r: -r["total_value"]
	)
