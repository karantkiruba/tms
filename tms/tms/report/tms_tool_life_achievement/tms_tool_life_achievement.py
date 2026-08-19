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
		{"label": _("Removal"), "fieldname": "name", "fieldtype": "Link",
		 "options": "TMS Tool Removal", "width": 150},
		{"label": _("Removal Date"), "fieldname": "removal_date", "fieldtype": "Date",
		 "width": 110},
		{"label": _("CPC Component"), "fieldname": "cpc_component", "fieldtype": "Link",
		 "options": "CPC Component", "width": 180},
		{"label": _("Machine"), "fieldname": "machine", "fieldtype": "Link",
		 "options": "TMS Customer Machine", "width": 150},
		{"label": _("Tool"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item",
		 "width": 170},
		{"label": _("Serial"), "fieldname": "serial_no", "fieldtype": "Data", "width": 160},
		{"label": _("Condition"), "fieldname": "condition_name", "fieldtype": "Data",
		 "width": 130},
		{"label": _("Regrinds"), "fieldname": "regrind_cycle", "fieldtype": "Int", "width": 80},
		{"label": _("Planned Life"), "fieldname": "planned_tool_life", "fieldtype": "Float",
		 "width": 110},
		{"label": _("Actual Life"), "fieldname": "actual_tool_life", "fieldtype": "Float",
		 "width": 110},
		{"label": _("Achievement %"), "fieldname": "life_achievement_pct", "fieldtype": "Percent",
		 "width": 120},
		{"label": _("Status"), "fieldname": "tool_life_status", "fieldtype": "Data",
		 "width": 120},
		{"label": _("Removal Reason"), "fieldname": "removal_reason", "fieldtype": "Data",
		 "width": 160},
	]


def get_data(filters):
	conditions = ["r.docstatus = 1", "r.removal_date between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.tms_location:
		conditions.append("r.tms_location = %(tms_location)s")
		values["tms_location"] = filters.tms_location
	if filters.cpc_component:
		conditions.append("r.cpc_component = %(cpc_component)s")
		values["cpc_component"] = filters.cpc_component
	if filters.status:
		conditions.append("r.tool_life_status = %(status)s")
		values["status"] = filters.status

	return frappe.db.sql(
		"""
		select r.name, r.removal_date, r.cpc_component, r.machine, r.item_code, r.serial_no,
		       r.regrind_cycle, r.planned_tool_life, r.actual_tool_life,
		       r.life_achievement_pct, r.tool_life_status, r.removal_reason,
		       c.condition_name
		from `tabTMS Tool Removal` r
		left join tabItem i on i.name = r.item_code
		left join `tabTMS Tool Condition` c on c.name = i.tms_tool_condition
		where {conditions}
		order by r.removal_date desc
		""".format(conditions=" and ".join(conditions)),
		values, as_dict=True,
	)
