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
		{"label": _("Tool Registration"), "fieldname": "name", "fieldtype": "Link",
		 "options": "TMS Tool Type", "width": 170},
		{"label": _("Tool Name"), "fieldname": "tool_type", "fieldtype": "Data",
		 "width": 110},
		{"label": _("Physical Tool Code"), "fieldname": "physical_tool_code", "fieldtype": "Data","width": 160},
		{"label": _("Description"), "fieldname": "tool_description", "fieldtype": "Data",
		 "width": 170},
		{"label": _("Standard Cost"), "fieldname": "standard_new_tool_cost",
		 "fieldtype": "Currency", "width": 140},
		{"label": _("Avg Purchase Cost"), "fieldname": "actual_avg_purchase_cost",
		 "fieldtype": "Currency", "width": 160},
		{"label": _("Last Purchase"), "fieldname": "last_purchase_cost", "fieldtype": "Currency",
		 "width": 140},
		{"label": _("Last Purchased"), "fieldname": "last_purchase_date", "fieldtype": "Date",
		 "width": 120},
		{"label": _("Qty Purchased"), "fieldname": "purchase_qty", "fieldtype": "Float",
		 "width": 120},
		{"label": _("Variance"), "fieldname": "variance", "fieldtype": "Currency", "width": 120},
		{"label": _("Variance %"), "fieldname": "cost_variance_pct", "fieldtype": "Percent",
		 "width": 120},
		{"label": _("Current Stock Value"), "fieldname": "stock_value", "fieldtype": "Currency",
		 "width": 160},
	]


def get_data(filters):
	"""Section 45.3. Standard is the PFEP planning benchmark; actual comes from
	submitted Purchase Receipts, never from a typed figure."""
	conditions = ["1 = 1"]
	values = {}

	if filters.tool_type:
		conditions.append("tr.tool_type = %(tool_type)s")
		values["tool_type"] = filters.tool_type
	if filters.regrindable_only:
		conditions.append("tr.is_regrindable = 1")

	rows = frappe.db.sql(
		"""
		select tr.name, tr.tool_type,tr.physical_tool_code, tr.tool_description, tr.standard_new_tool_cost,
		       tr.actual_avg_purchase_cost, tr.last_purchase_cost, tr.last_purchase_date,
		       tr.purchase_qty, tr.cost_variance_pct
		from `tabTMS Tool Registration` tr
		INNER JOIN `tabTMS Tool Type` tt ON tt.name = tr.tool_type
		where {conditions}
		order by abs(coalesce(tr.cost_variance_pct, 0)) desc, tr.name
		""".format(conditions=" and ".join(conditions)),
		values, as_dict=True,
	)

	for row in rows:
		# nothing purchased means there is no actual to compare against
		row.variance = (
			flt(row.actual_avg_purchase_cost) - flt(row.standard_new_tool_cost)
			if flt(row.purchase_qty) else 0
		)
		row.stock_value = flt(frappe.db.sql(
			"""
			select coalesce(sum(b.stock_value), 0)
			from tabBin b inner join tabItem i on i.name = b.item_code
			where i.custom_tms_tool_registration = %(tool_registration)s
			""",
			{"tool_registration": row.name},
		)[0][0])

	if filters.variance_only:
		rows = [r for r in rows if flt(r.variance)]

	return rows
