# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from tms.utils import validation as tms_validate


class TMSProductionDeclaration(Document):
	"""Customer production declaration (BRS section 20).

	Accepted quantity is derived from the billing rules on the CPC Contract, and
	each line carries its own billed and unbilled quantity so the same production
	can never be billed twice (BRS section 35, rule 20).
	"""

	def validate(self):
		tms_validate.validate_active_contract(self.cpc_contract, None, self.posting_date)
		self.validate_rows()
		self.set_totals()

	def validate_rows(self):
		if not self.items:
			frappe.throw(_("At least one production row is required."))

		contract = frappe.get_cached_doc("CPC Contract", self.cpc_contract)
		rules = {}
		for row in contract.components:
			rules.setdefault(row.cpc_component, row)

		for row in self.items:
			rule = rules.get(row.cpc_component)
			if not rule:
				frappe.throw(
					_("Row {0}: CPC Component {1} is not covered by CPC Contract {2}.").format(
						row.idx, row.cpc_component, self.cpc_contract
					)
				)

			tms_validate.validate_machine_operation(row.cpc_component, row.machine, rule.operation) 				if row.machine and rule.operation else None

			row.accepted_qty = self.calculate_accepted_qty(row, rule)

			if row.customer_confirmed_qty in (None, 0) and not self.confirmation_status == "Pending":
				row.customer_confirmed_qty = row.accepted_qty

			if flt(row.customer_confirmed_qty) > flt(row.gross_production):
				frappe.throw(
					_("Row {0}: Customer Confirmed Quantity cannot exceed Gross Production.").format(row.idx)
				)

			row.billable_qty = self.get_billable_qty(row, contract)
			row.cpc_rate = self.get_rate(row)
			row.unbilled_qty = flt(row.billable_qty) - flt(row.billed_qty)
			row.billing_status = self.get_billing_status(row)

	def calculate_accepted_qty(self, row, rule):
		"""Gross less whatever the contract treats as non-billable."""
		deduction = flt(row.non_billable_qty)

		if (rule.rejection_billing_rule or "Not Billable") == "Not Billable":
			deduction += flt(row.rejection_qty)
		if (rule.rework_billing_rule or "Not Billable") == "Not Billable":
			deduction += flt(row.rework_qty)

		accepted = flt(row.gross_production) - deduction
		if accepted < 0:
			frappe.throw(
				_("Row {0}: deductions exceed the gross production quantity.").format(row.idx)
			)
		return accepted

	def get_billable_qty(self, row, contract):
		if contract.billing_basis == "Accepted Production":
			return flt(row.accepted_qty)
		return flt(row.customer_confirmed_qty)

	def get_rate(self, row):
		from tms.tms.doctype.cpc_contract.cpc_contract import get_cpc_rate

		try:
			rate = get_cpc_rate(
				row.cpc_component, row.production_date or self.posting_date,
				machine=row.machine, cpc_contract=self.cpc_contract
			)
			return flt(rate.cpc_rate)
		except frappe.ValidationError:
			return 0

	@staticmethod
	def get_billing_status(row):
		billable = flt(row.billable_qty)
		billed = flt(row.billed_qty)

		if billed <= 0:
			return "Unbilled"
		if billed >= billable:
			return "Fully Billed"
		return "Partially Billed"

	def set_totals(self):
		self.total_gross_production = sum(flt(r.gross_production) for r in self.items)
		self.total_accepted_qty = sum(flt(r.accepted_qty) for r in self.items)
		self.total_confirmed_qty = sum(flt(r.customer_confirmed_qty) for r in self.items)
		self.total_billable_qty = sum(flt(r.billable_qty) for r in self.items)

	def on_cancel(self):
		billed = [r.idx for r in self.items if flt(r.billed_qty) > 0]
		if billed:
			frappe.throw(
				_("Rows {0} have already been billed. Cancel the CPC Billing Statement first.").format(
					", ".join(str(i) for i in billed)
				)
			)
