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
		{"label": _("Date"), "fieldname": "production_date", "fieldtype": "Date", "width": 100},
		{"label": _("Declaration"), "fieldname": "parent", "fieldtype": "Link",
		 "options": "TMS Production Declaration", "width": 150},
		{"label": _("CPC Component"), "fieldname": "cpc_component", "fieldtype": "Link",
		 "options": "CPC Component", "width": 180},
		{"label": _("Machine"), "fieldname": "machine", "fieldtype": "Link",
		 "options": "TMS Customer Machine", "width": 140},
		{"label": _("Gross"), "fieldname": "gross_production", "fieldtype": "Float",
		 "width": 100},
		{"label": _("Rejected"), "fieldname": "rejection_qty", "fieldtype": "Float",
		 "width": 100},
		{"label": _("Rework"), "fieldname": "rework_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Accepted"), "fieldname": "accepted_qty", "fieldtype": "Float",
		 "width": 100},
		{"label": _("Confirmed"), "fieldname": "customer_confirmed_qty", "fieldtype": "Float",
		 "width": 110},
		{"label": _("Rate"), "fieldname": "cpc_rate", "fieldtype": "Currency", "width": 90},
		{"label": _("Billable Value"), "fieldname": "billable_value", "fieldtype": "Currency",
		 "width": 130},
		{"label": _("Billed"), "fieldname": "billed_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Unbilled"), "fieldname": "unbilled_qty", "fieldtype": "Float",
		 "width": 100},
		{"label": _("Billing Status"), "fieldname": "billing_status", "fieldtype": "Data",
		 "width": 130},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link","options": "Branch","width": 130}
	]


def get_data(filters):
	conditions = ["d.docstatus = 1", "i.production_date between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.tms_location:
		conditions.append("d.tms_location = %(tms_location)s")
		values["tms_location"] = filters.tms_location
	if filters.cpc_component:
		conditions.append("i.cpc_component = %(cpc_component)s")
		values["cpc_component"] = filters.cpc_component
	if filters.billing_status:
		conditions.append("i.billing_status = %(billing_status)s")
		values["billing_status"] = filters.billing_status

	rows = frappe.db.sql(
		"""
		select i.production_date, i.parent, i.cpc_component, i.machine,d.branch,
		       i.gross_production, i.rejection_qty, i.rework_qty, i.accepted_qty,
		       i.customer_confirmed_qty, i.cpc_rate, i.billable_qty,
		       i.billed_qty, i.unbilled_qty, i.billing_status
		from `tabTMS Production Declaration Item` i
		inner join `tabTMS Production Declaration` d on d.name = i.parent
		where {conditions}
		order by i.production_date desc, i.cpc_component
		""".format(conditions=" and ".join(conditions)),
		values, as_dict=True,
	)

	for row in rows:
		row.billable_value = flt(row.billable_qty) * flt(row.cpc_rate)
	return rows
