# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt
"""Actual tool cost, rolled up from purchase history.

The standard cost on a Tool Type is the planning benchmark (BRS section 11.4).
This module supplies the other half of that comparison: what the company has
actually paid, taken from submitted Purchase Receipts rather than typed in.
"""

import frappe
from frappe.utils import flt


def get_purchase_cost(tool_type):
	"""Average, latest and total purchased quantity for one tool type."""
	row = frappe.db.sql(
		"""
		select
			sum(pri.base_net_amount) as total_value,
			sum(pri.stock_qty) as total_qty,
			max(pr.posting_date) as last_date
		from `tabPurchase Receipt Item` pri
		inner join `tabPurchase Receipt` pr on pr.name = pri.parent
		inner join tabItem i on i.name = pri.item_code
		where pr.docstatus = 1 and i.tms_tool_type = %(tool_type)s
		""",
		{"tool_type": tool_type},
		as_dict=True,
	)[0]

	if not row or not flt(row.total_qty):
		return frappe._dict({"average": 0, "last": 0, "last_date": None, "qty": 0})

	last = frappe.db.sql(
		"""
		select pri.base_rate
		from `tabPurchase Receipt Item` pri
		inner join `tabPurchase Receipt` pr on pr.name = pri.parent
		inner join tabItem i on i.name = pri.item_code
		where pr.docstatus = 1 and i.tms_tool_type = %(tool_type)s
		order by pr.posting_date desc, pr.creation desc
		limit 1
		""",
		{"tool_type": tool_type},
	)

	return frappe._dict({
		"average": flt(row.total_value) / flt(row.total_qty),
		"last": flt(last[0][0]) if last else 0,
		"last_date": row.last_date,
		"qty": flt(row.total_qty),
	})


def update_tool_type_cost(tool_type):
	"""Write the purchase rollup onto the Tool Type."""
	if not tool_type or not frappe.db.exists("TMS Tool Type", tool_type):
		return

	cost = get_purchase_cost(tool_type)
	standard = flt(frappe.db.get_value("TMS Tool Type", tool_type, "standard_new_tool_cost"))

	# with nothing purchased there is no actual to compare, so no variance either
	variance = 0
	if standard and cost.qty:
		variance = (cost.average - standard) / standard * 100

	frappe.db.set_value("TMS Tool Type", tool_type, {
		"actual_avg_purchase_cost": cost.average,
		"last_purchase_cost": cost.last,
		"last_purchase_date": cost.last_date,
		"purchase_qty": cost.qty,
		"cost_variance_pct": variance,
	}, update_modified=False)

	return cost


def update_from_purchase_receipt(doc, method=None):
	"""Refresh every tool type touched by a Purchase Receipt."""
	tool_types = set()
	for row in doc.get("items", []):
		tool_type = frappe.db.get_value("Item", row.item_code, "tms_tool_type")
		if tool_type:
			tool_types.add(tool_type)

	for tool_type in tool_types:
		update_tool_type_cost(tool_type)


@frappe.whitelist()
def refresh_all_tool_costs():
	"""Rebuild the rollup for every tool type. Useful after a data migration."""
	updated = 0
	for tool_type in frappe.get_all("TMS Tool Type", pluck="name"):
		update_tool_type_cost(tool_type)
		updated += 1
	frappe.db.commit()
	return updated
