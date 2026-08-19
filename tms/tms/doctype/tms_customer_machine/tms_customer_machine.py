# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TMSCustomerMachine(Document):
	def validate(self):
		self.validate_line_location()

	def validate_line_location(self):
		if not self.production_line:
			return
		line_location = frappe.db.get_value("TMS Production Line", self.production_line, "tms_location")
		if line_location != self.tms_location:
			frappe.throw(
				_("Production Line {0} belongs to TMS Location {1}, not {2}.").format(
					self.production_line, line_location, self.tms_location
				)
			)
