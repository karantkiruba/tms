# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CPCComponent(Document):
	def validate(self):
		self.validate_operations()

	def validate_operations(self):
		seen = set()
		for row in self.operations:
			machine_location = frappe.db.get_value("TMS Customer Machine", row.machine, "tms_location")
			if machine_location != self.tms_location:
				frappe.throw(
					_("Row {0}: Machine {1} belongs to TMS Location {2}, not {3}.").format(
						row.idx, row.machine, machine_location, self.tms_location
					)
				)

			key = (row.machine, row.operation)
			if key in seen:
				frappe.throw(
					_("Row {0}: Machine {1} and Operation {2} are repeated.").format(
						row.idx, row.machine, row.operation
					)
				)
			seen.add(key)

	def is_valid_machine_operation(self, machine, operation):
		"""True when the machine/operation pair is defined for this component."""
		return any(r.machine == machine and r.operation == operation for r in self.operations)
