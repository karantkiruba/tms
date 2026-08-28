# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


WAREHOUSE_ROLES = (
	("main_warehouse", "Main"),
	("shopfloor_warehouse", "Shopfloor"),
	("used_tool_warehouse", "Used Tool"),
	("head_office_warehouse", "Head Office"),
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Warehouse Role"), "fieldname": "warehouse_role", "fieldtype": "Data",
		 "width": 130},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link",
		 "options": "Warehouse", "width": 200},
		{"label": _("Tool Type"), "fieldname": "tool_type", "fieldtype": "Link",
		 "options": "TMS Tool Type", "width": 150},
		{"label": _("Condition"), "fieldname": "condition_name", "fieldtype": "Data",
		 "width": 150},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item",
		 "width": 200},
		{"label": _("Physical Tool"), "fieldname": "physical_tool_code", "fieldtype": "Data",
		 "width": 140},
		{"label": _("Qty"), "fieldname": "actual_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Valuation Rate"), "fieldname": "valuation_rate", "fieldtype": "Currency",
		 "width": 120},
		{"label": _("Stock Value"), "fieldname": "stock_value", "fieldtype": "Currency",
		 "width": 130},
	]


def get_warehouse_map(tms_location):
	"""Warehouse to its role, so stock reads as a TMS position not a raw bin list."""
	locations = frappe.get_all(
		"TMS Customer Location",
		filters={"name": tms_location} if tms_location else {},
		fields=["name"] + [f for f, _label in WAREHOUSE_ROLES],
	)
	mapping = {}
	for loc in locations:
		for field, label in WAREHOUSE_ROLES:
			if loc.get(field):
				mapping[loc[field]] = label
	return mapping


def get_data(filters):
	warehouse_map = get_warehouse_map(filters.tms_location)
	#if not warehouse_map:
		#return []

	conditions = []
	values = {}

	if filters.tool_type:
		conditions.append("i.tms_tool_type = %(tool_type)s")
		values["tool_type"] = filters.tool_type
	if filters.hide_zero:
		conditions.append("b.actual_qty != 0")

	where_clause = ""
	if conditions:
		where_clause = "WHERE " + " AND ".join(conditions)

	rows = frappe.db.sql(
		f"""
		select b.warehouse, b.item_code, b.actual_qty, b.valuation_rate,
		       b.stock_value, i.tms_tool_type as tool_type,w.warehouse_type as warehouse_role,
		       i.tms_physical_tool_code as physical_tool_code,
		       c.condition_name
		from tabBin b
		inner join tabItem i on i.name = b.item_code
                 
    LEFT JOIN tabWarehouse w
        ON w.name = b.warehouse
		left join `tabTMS Tool Condition` c on c.name = i.tms_tool_condition
		{where_clause}
		order by b.warehouse, i.tms_tool_type, c.sort_order
		""",
		values, as_dict=True,
	)

	#for row in rows:
		#row.warehouse_role = warehouse_map.get(row.warehouse,"")
	return rows
