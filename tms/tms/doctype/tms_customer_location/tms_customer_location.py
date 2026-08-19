# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

WAREHOUSE_FIELDS = ("main_warehouse", "shopfloor_warehouse", "used_tool_warehouse")


class TMSCustomerLocation(Document):
	def validate(self):
		self.validate_distinct_warehouses()
		self.validate_warehouse_company()

	def validate_distinct_warehouses(self):
		seen = {}
		for field in WAREHOUSE_FIELDS:
			warehouse = self.get(field)
			if not warehouse:
				continue
			if warehouse in seen:
				frappe.throw(
					_("{0} and {1} cannot both be set to {2}. Each TMS warehouse must be distinct.").format(
						_(self.meta.get_label(seen[warehouse])), _(self.meta.get_label(field)), warehouse
					)
				)
			seen[warehouse] = field

	def validate_warehouse_company(self):
		if not self.company:
			return
		for field in WAREHOUSE_FIELDS:
			warehouse = self.get(field)
			if not warehouse:
				continue
			company = frappe.db.get_value("Warehouse", warehouse, "company")
			if company != self.company:
				frappe.throw(
					_("Warehouse {0} belongs to company {1}, not {2}.").format(warehouse, company, self.company)
				)


def get_tms_warehouses(tms_location):
	"""Return the three operating warehouses for a TMS Customer Location."""
	if not tms_location:
		return frappe._dict()
	return frappe.db.get_value(
		"TMS Customer Location", tms_location, list(WAREHOUSE_FIELDS), as_dict=True
	) or frappe._dict()
