# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TMSToolType(Document):
	pass
	#def validate(self):
		#self.validate_regrind_settings()
		#self.validate_life()

	#def validate_regrind_settings(self):
		#if not self.is_regrindable:
		#	self.max_regrind_count = 0
		#	self.planned_reground_tool_life = 0
		#	self.standard_regrind_cost = 0
		#	return

	#	if not self.max_regrind_count or self.max_regrind_count < 1:
	#		frappe.throw(_("Maximum Regrind Count must be at least 1 for a regrindable tool type."))

	#@frappe.whitelist()
	#def refresh_purchase_cost(self):
	#	"""Pull the actual purchase cost for this tool type from receipt history."""
	#	from tms.utils.costing import update_tool_type_cost

	#	cost = update_tool_type_cost(self.name)
	#	self.reload()
	#	return cost

	#def validate_life(self):
		#for field in ("planned_new_tool_life", "planned_reground_tool_life"):
			#if (self.get(field) or 0) < 0:
				#frappe.throw(_("{0} cannot be negative.").format(_(self.meta.get_label(field))))
