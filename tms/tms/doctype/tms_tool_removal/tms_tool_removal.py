# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from tms.utils import validation as tms_validate


class TMSToolRemoval(Document):
	"""Removal of the primary tool and tool-life achievement (BRS sections 21 to 23)."""

	def validate(self):
		self.fetch_from_installation()
		self.calculate_tool_life()

	def fetch_from_installation(self):
		installation = frappe.get_doc("TMS Tool Installation", self.tool_installation)

		if installation.docstatus != 1:
			frappe.throw(_("Tool Installation {0} is not submitted.").format(self.tool_installation))

		self.tool_issue = installation.tool_issue
		self.item_code = installation.item_code
		self.serial_no = installation.serial_no
		self.physical_tool_code = installation.physical_tool_code
		self.tool_type = installation.tool_type
		self.cpc_component = installation.cpc_component
		self.machine = installation.machine
		self.operation = installation.operation
		self.tms_location = installation.tms_location
		self.customer = installation.customer
		self.installation_date = installation.installation_date
		self.starting_production_counter = installation.starting_production_counter
		self.planned_tool_life = installation.planned_tool_life
		self.regrind_cycle = installation.regrind_cycle

	def calculate_tool_life(self):
		"""Actual life is production at removal less production at installation."""
		if flt(self.ending_production_counter) < flt(self.starting_production_counter):
			frappe.throw(
				_("Ending Production Counter ({0}) cannot be lower than the Starting Production "
				  "Counter ({1}).").format(
					self.ending_production_counter, self.starting_production_counter
				)
			)

		self.actual_tool_life = flt(self.ending_production_counter) - flt(
			self.starting_production_counter
		)

		if flt(self.planned_tool_life):
			self.life_achievement_pct = (
				flt(self.actual_tool_life) / flt(self.planned_tool_life) * 100
			)
			self.tool_life_status = tms_validate.get_tool_life_status(self.life_achievement_pct)
		else:
			self.life_achievement_pct = 0
			self.tool_life_status = "Not Measured"

	def on_submit(self):
		frappe.db.set_value(
			"TMS Tool Installation",
			self.tool_installation,
			{"installation_status": "Removed", "removal_reference": self.name},
		)

	def on_cancel(self):
		frappe.db.set_value(
			"TMS Tool Installation",
			self.tool_installation,
			{"installation_status": "Installed", "removal_reference": None},
		)
