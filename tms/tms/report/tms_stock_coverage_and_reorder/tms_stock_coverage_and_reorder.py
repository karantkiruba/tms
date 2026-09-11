# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


from tms.utils import planning


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("CPC Component"), "fieldname": "cpc_component", "fieldtype": "Link",
		 "options": "CPC Component", "width": 180},
		{"label": _("Tool Type"), "fieldname": "tool_type", "fieldtype": "Link",
		 "options": "TMS Tool Type", "width": 160},
		{"label": _("Machine"), "fieldname": "machine", "fieldtype": "Link",
		 "options": "TMS Customer Machine", "width": 140},
		{"label": _("Gross Req"), "fieldname": "gross_requirement", "fieldtype": "Float",
		 "width": 110},
		{"label": _("Available"), "fieldname": "available_qty", "fieldtype": "Float",
		 "width": 100},
		{"label": _("From Regrind"), "fieldname": "expected_regrind_qty", "fieldtype": "Float",
		 "width": 120},
		{"label": _("Open Transfer"), "fieldname": "open_transfer_qty", "fieldtype": "Float",
		 "width": 120},
		{"label": _("Open Purchase"), "fieldname": "open_purchase_qty", "fieldtype": "Float",
		 "width": 120},
		{"label": _("Net Requirement"), "fieldname": "net_requirement", "fieldtype": "Float",
		 "width": 140},
		{"label": _("Safe Running Days"), "fieldname": "safe_running_days", "fieldtype": "Float",
		 "precision": 1, "width": 150},
		{"label": _("Stock Status"), "fieldname": "stock_status", "fieldtype": "Data",
		 "width": 130},
		{"label": _("Recommended Action"), "fieldname": "recommended_action", "fieldtype": "Data",
		 "width": 180},
	]


def get_data(filters):
	"""Sections 41 and 42, computed live from PFEP and the current stock position."""
	rows = planning.build_requirement_rows(
		source_warehouse=filters.source_warehouse,
		target_warehouse=filters.target_warehouse,
		cpc_component=filters.cpc_component,
		posting_date=frappe.utils.nowdate(),
		monthly_volume_override=filters.monthly_production_plan,
		working_days=filters.working_days or 26,
	)

	if filters.shortages_only:
		rows = [r for r in rows if flt(r["net_requirement"]) > 0]

	return sorted(rows, key=lambda r: (-flt(r["net_requirement"]), r["tool_type"] or ""))
