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
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date",
		 "width": 110},
		{"label": _("Stock Entry"), "fieldname": "stock_entry", "fieldtype": "Link",
		 "options": "Stock Entry", "width": 150},
		{"label": _("Purpose"), "fieldname": "purpose", "fieldtype": "Data", "width": 140},
		{"label": _("TMS Transaction"), "fieldname": "tms_reference_doctype", "fieldtype": "Data",
		 "width": 180},
		{"label": _("Reference"), "fieldname": "tms_reference_name", "fieldtype": "Dynamic Link",
		 "options": "tms_reference_doctype", "width": 160},
		{"label": _("CPC Component"), "fieldname": "tms_cpc_component", "fieldtype": "Link",
		 "options": "CPC Component", "width": 170},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item",
		 "width": 170},
		{"label": _("From"), "fieldname": "s_warehouse", "fieldtype": "Link",
		 "options": "Warehouse", "width": 170},
		{"label": _("To"), "fieldname": "t_warehouse", "fieldtype": "Link",
		 "options": "Warehouse", "width": 170},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("Value"), "fieldname": "amount", "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	conditions = ["se.docstatus = 1", "se.tms_reference_name is not null",
	              "se.posting_date between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.tms_location:
		conditions.append("se.tms_location = %(tms_location)s")
		values["tms_location"] = filters.tms_location
	if filters.reference_type:
		conditions.append("se.tms_reference_doctype = %(reference_type)s")
		values["reference_type"] = filters.reference_type

	return frappe.db.sql(
		"""
		select se.posting_date, se.name as stock_entry, se.purpose,
		       se.tms_reference_doctype, se.tms_reference_name, se.tms_cpc_component,
		       sed.item_code, sed.s_warehouse, sed.t_warehouse, sed.qty, sed.amount
		from `tabStock Entry Detail` sed
		inner join `tabStock Entry` se on se.name = sed.parent
		where {conditions}
		order by se.posting_date desc, se.name, sed.idx
		""".format(conditions=" and ".join(conditions)),
		values, as_dict=True,
	)
