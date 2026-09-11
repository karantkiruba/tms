# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
import re

def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Cycle"), "fieldname": "name", "fieldtype": "Link",
		 "options": "TMS Regrind Cycle", "width": 140},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 140},
		{"label": _("Physical Tool"), "fieldname": "physical_tool_code", "fieldtype": "Data",
		 "width": 150},
		{"label": _("Tool Type"), "fieldname": "tool_type", "fieldtype": "Link",
		 "options": "TMS Tool Type", "width": 150},
		{"label": _("Incoming"), "fieldname": "source_item", "fieldtype": "Link",
		 "options": "Item", "width": 170},
		{"label": _("Incoming Serial"), "fieldname": "source_serial_no", "fieldtype": "Data",
		 "width": 170},
		{"label": _("Cycle No"), "fieldname": "cycle_number", "fieldtype": "Int", "width": 90},
		{"label": _("Reground Serial"), "fieldname": "output_serial_no", "fieldtype": "Data",
		 "width": 180},
		{"label": _("Completed"), "fieldname": "completed_regrind_count", "fieldtype": "Int",
		 "width": 100},
		{"label": _("Maximum"), "fieldname": "max_regrind_count", "fieldtype": "Int",
		 "width": 90},
		{"label": _("Remaining"), "fieldname": "remaining_regrinds", "fieldtype": "Int",
		 "width": 100},
		{"label": _("Regrind Cost"), "fieldname": "regrind_cost", "fieldtype": "Currency",
		 "width": 130},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date",
		 "width": 110},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link","options": "Branch"}
	]


def get_data(filters):
	conditions = ["c.docstatus = 1"]
	values = {}

	if filters.tms_location:
		conditions.append("c.tms_location = %(tms_location)s")
		values["tms_location"] = filters.tms_location
	if filters.status:
		conditions.append("c.status = %(status)s")
		values["status"] = filters.status
	if filters.near_max_only:
		# one cycle left or none, which is when engineering wants advance warning
		conditions.append("c.remaining_regrinds <= 1")

	data =  frappe.db.sql(
		"""
		select c.name, c.status, c.physical_tool_code, c.tool_type, c.source_item,
		       c.source_serial_no, c.cycle_number, c.output_serial_no,
		       c.completed_regrind_count, c.max_regrind_count, c.remaining_regrinds,
		       c.regrind_cost, c.posting_date,c.branch
		from `tabTMS Regrind Cycle` c
		where {conditions}
		order by c.posting_date desc, c.physical_tool_code
		""".format(conditions=" and ".join(conditions)),
		values, as_dict=True,
	)
	result = []
	for row in data:
		output_serials = row.output_serial_no
		if output_serials:
			serials = re.split(r"[\s,]+", output_serials.strip())
			serials = [serial for serial in serials if serial]
		else:
			serials = [""]

		for serial in serials:
			new_row = row.copy()
			new_row.output_serial_no = serial
			result.append(new_row)
	return result
