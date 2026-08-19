# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, cint

from tms.utils import planning


class TMSToolRequirement(Document):
	"""Replenishment planning for a customer location (BRS sections 13, 41 and 42).

	The requirement is derived from the approved PFEP and the planned production
	volume, then netted against everything already available or already on its
	way, so the site only asks for what is genuinely short.
	"""

	def validate(self):
		self.set_totals()

	def set_totals(self):
		self.total_net_requirement = sum(flt(r.net_requirement) for r in self.items)
		self.total_requested_qty = sum(flt(r.requested_qty) for r in self.items)
		self.shortage_lines = len([r for r in self.items if flt(r.net_requirement) > 0])

	@frappe.whitelist()
	def calculate_requirement(self):
		"""Build the requirement rows from PFEP and current stock position."""
		if not self.tms_location:
			frappe.throw(_("Select the TMS Customer Location first."))

		rows = planning.build_requirement_rows(
			tms_location=self.tms_location,
			cpc_component=self.cpc_component,
			posting_date=self.posting_date,
			monthly_volume_override=self.monthly_production_plan,
			working_days=cint(self.working_days) or 26,
		)

		self.set("items", [])
		for row in rows:
			self.append("items", row)

		self.set_totals()
		return len(rows)

	@frappe.whitelist()
	def make_material_request(self):
		"""Raise a standard ERPNext Material Request for the requested quantities."""
		if self.docstatus != 1:
			frappe.throw(_("Submit the requirement before raising a Material Request."))
		if self.material_request:
			frappe.throw(_("Material Request {0} already exists.").format(self.material_request))

		lines = [r for r in self.items if flt(r.requested_qty) > 0 and r.item_code]
		if not lines:
			frappe.throw(_("No rows carry a requested quantity against an item."))

		warehouse = frappe.db.get_value("TMS Customer Location", self.tms_location,
		                                "main_warehouse")

		mr = frappe.new_doc("Material Request")
		mr.material_request_type = "Material Transfer"
		mr.company = self.company
		mr.transaction_date = self.posting_date
		mr.schedule_date = self.required_date or self.posting_date

		for row in lines:
			mr.append("items", {
				"item_code": row.item_code,
				"qty": flt(row.requested_qty),
				"warehouse": warehouse,
				"schedule_date": self.required_date or self.posting_date,
			})

		mr.insert(ignore_permissions=True)

		self.db_set("material_request", mr.name)
		self.db_set("status", "Requested")
		return mr.name

	def on_submit(self):
		self.db_set("status", "Approved")

	def on_cancel(self):
		if self.material_request and frappe.db.get_value(
			"Material Request", self.material_request, "docstatus"
		) == 1:
			frappe.throw(
				_("Material Request {0} is submitted. Cancel it before cancelling this requirement.").format(
					self.material_request
				)
			)
		self.db_set("status", "Cancelled")
