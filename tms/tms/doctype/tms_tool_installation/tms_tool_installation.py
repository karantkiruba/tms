# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from tms.utils import validation as tms_validate


class TMSToolInstallation(Document):
	"""Installation of the primary tool on a machine (BRS section 19).

	Only the primary tool is tracked. Inserts and taps are managed by quantity
	and value through Tool Issue (BRS section 32).
	"""

	def validate(self):
		#self.validate_against_issue()
		self.validate_not_already_installed()
		self.set_life_reference()

	def validate_against_issue(self):
		if not self.tool_issue:
			return

		row = frappe.db.get_value(
			"TMS Tool Issue Item",
			{"parent": self.tool_issue, "item_code": self.item_code},
			["name", "is_primary_tool", "planned_tool_life", "regrind_cycle", "serial_no"],
			as_dict=True,
		)
		if not row:
			frappe.throw(
				_("Item {0} was not issued on Tool Issue {1}.").format(self.item_code, self.tool_issue)
			)

		if not row.is_primary_tool:
			frappe.throw(
				_("Item {0} is not the primary tool on Tool Issue {1}. "
				  "Installation is tracked for the primary tool only.").format(
					self.item_code, self.tool_issue
				)
			)

	def validate_not_already_installed(self):
		"""A serialised tool cannot be installed on two machines at once."""
		if not self.serial_no:
			return

		existing = frappe.db.exists(
			"TMS Tool Installation",
			{
				"serial_no": self.serial_no,
				"installation_status": "Installed",
				"docstatus": 1,
				"name": ("!=", self.name),
			},
		)
		if existing:
			frappe.throw(
				_("Serial {0} is still installed under {1}. Record its removal first.").format(
					self.serial_no, existing
				),
				title=_("Tool Already Installed"),
			)

	def set_life_reference(self):
		if self.planned_tool_life:
			return

		info = tms_validate.get_item_tool_info(self.item_code)
		flags = tms_validate.get_condition_flags(info.get("tms_tool_condition"))
		tool_type = frappe.db.get_value(
			"TMS Tool Registration", info.get("custom_tms_tool_registration"),
			["planned_new_tool_life", "planned_reground_tool_life"], as_dict=True
		)
		if not tool_type:
			return

		self.planned_tool_life = (
			tool_type.planned_reground_tool_life
			if flags.get("is_regrind_output")
			else tool_type.planned_new_tool_life
		)

	def before_submit(self):
		self.installation_status = "Installed"
