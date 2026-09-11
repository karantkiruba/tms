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
		{"label": _("Physical Tool"), "fieldname": "physical_tool_code", "fieldtype": "Data",
		 "width": 150},
		{"label": _("Tool Type"), "fieldname": "tool_type", "fieldtype": "Link",
		 "options": "TMS Tool Type", "width": 150},
		{"label": _("Current Condition"), "fieldname": "condition_name", "fieldtype": "Data",
		 "width": 150},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item",
		 "width": 190},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link",
		 "options": "Warehouse", "width": 190},
		{"label": _("Qty"), "fieldname": "actual_qty", "fieldtype": "Float", "width": 70},
		{"label": _("Serial"), "fieldname": "serial_no", "fieldtype": "Link",
		 "options": "Serial No", "width": 180},
		{"label": _("Regrinds Done"), "fieldname": "regrind_cycle", "fieldtype": "Int",
		 "width": 110},
		{"label": _("Max Regrinds"), "fieldname": "max_regrind_count", "fieldtype": "Int",
		 "width": 110},
		{"label": _("Remaining"), "fieldname": "remaining_regrinds", "fieldtype": "Int",
		 "width": 100},
		{"label": _("Stock Value"), "fieldname": "stock_value", "fieldtype": "Currency",
		 "width": 120},
	]


def get_data(filters):
	conditions = ["i.tms_is_tool = 1", "i.tms_physical_tool_code is not null"]
	values = {}

	if filters.tool_type:
		conditions.append("i.tms_tool_type = %(tool_type)s")
		values["tool_type"] = filters.tool_type
	if filters.physical_tool_code:
		conditions.append("i.tms_physical_tool_code like %(code)s")
		values["code"] = "%" + filters.physical_tool_code + "%"

	join = "inner" if filters.only_in_stock else "left"

	rows = frappe.db.sql(
		"""
		select i.name as item_code, i.tms_physical_tool_code as physical_tool_code,
		       i.tms_tool_type as tool_type, c.condition_name, c.sort_order,
		       b.warehouse, b.actual_qty, b.stock_value,
		       tt.max_regrind_count
		from tabItem i
		left join `tabTMS Tool Condition` c on c.name = i.tms_tool_condition
		left join `tabTMS Tool Registration` tt on tt.name = i.custom_tms_tool_registration
		{join} join tabBin b on b.item_code = i.name and b.actual_qty > 0
		where {conditions}
		order by i.tms_physical_tool_code, c.sort_order
		""".format(conditions=" and ".join(conditions), join=join),
		values, as_dict=True,
	)

	for row in rows:
		serial = frappe.db.get_value(
			"Serial No",
			{"item_code": row.item_code, "warehouse": row.warehouse},
			["name", "tms_regrind_cycle"], as_dict=True,
		) if row.warehouse else None

		row.serial_no = serial.name if serial else None
		row.regrind_cycle = serial.tms_regrind_cycle if serial else 0
		row.remaining_regrinds = flt(row.max_regrind_count) - flt(row.regrind_cycle)

	return rows
