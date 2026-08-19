# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

OPEN_ENDED = "2999-12-31"


class CPCContract(Document):
	def validate(self):
		self.validate_dates()
		self.validate_components()
		self.validate_rate_periods()
		self.set_status()

	def validate_dates(self):
		if getdate(self.contract_end_date) < getdate(self.contract_start_date):
			frappe.throw(_("Contract End Date cannot be earlier than Contract Start Date."))

	def validate_components(self):
		if not self.components:
			frappe.throw(_("At least one CPC Component row is required."))

		for row in self.components:
			component = frappe.db.get_value(
				"CPC Component", row.cpc_component, ["tms_location", "customer"], as_dict=True
			)
			if not component:
				continue
			if component.tms_location != self.tms_location:
				frappe.throw(
					_("Row {0}: CPC Component {1} belongs to TMS Location {2}, not {3}.").format(
						row.idx, row.cpc_component, component.tms_location, self.tms_location
					)
				)

			if getdate(row.effective_from) < getdate(self.contract_start_date):
				frappe.throw(
					_("Row {0}: Effective From cannot be earlier than the Contract Start Date.").format(row.idx)
				)
			if row.effective_to and getdate(row.effective_to) < getdate(row.effective_from):
				frappe.throw(_("Row {0}: Effective To cannot be earlier than Effective From.").format(row.idx))

	def validate_rate_periods(self):
		"""A component/machine/operation may carry only one rate on any given date."""
		seen = {}
		for row in self.components:
			key = (row.cpc_component, row.machine or "", row.operation or "")
			start = getdate(row.effective_from)
			end = getdate(row.effective_to or OPEN_ENDED)

			for other_idx, other_start, other_end in seen.get(key, []):
				if start <= other_end and other_start <= end:
					frappe.throw(
						_("Row {0} overlaps row {1}: CPC Component {2} already has a rate "
						  "covering this period. Rates must be effective-dated without overlap.").format(
							row.idx, other_idx, row.cpc_component
						)
					)
			seen.setdefault(key, []).append((row.idx, start, end))

	def set_status(self):
		if self.docstatus == 2:
			self.status = "Cancelled"
		elif self.docstatus == 0:
			self.status = "Draft"
		elif getdate(self.contract_end_date) < getdate(frappe.utils.nowdate()):
			self.status = "Expired"
		else:
			self.status = "Active"

	def on_submit(self):
		self.set_status()

	def on_cancel(self):
		self.status = "Cancelled"


@frappe.whitelist()
def get_cpc_rate(cpc_component, posting_date, machine=None, operation=None, cpc_contract=None):
	"""Effective-dated CPC rate lookup.

	Prefers the most specific match (machine + operation), then machine, then component.
	Returns a dict with the rate, the contract and the contract row it came from.
	"""
	conditions = [
		"c.docstatus = 1",
		"c.status in ('Active', 'Expired')",
		"row.cpc_component = %(component)s",
		"row.effective_from <= %(date)s",
		"ifnull(row.effective_to, %(open_ended)s) >= %(date)s",
	]
	values = {
		"component": cpc_component,
		"date": posting_date,
		"open_ended": OPEN_ENDED,
		"machine": machine,
		"operation": operation,
	}
	if cpc_contract:
		conditions.append("c.name = %(contract)s")
		values["contract"] = cpc_contract

	rows = frappe.db.sql(
		"""
		select
			c.name as cpc_contract,
			row.name as contract_row,
			row.cpc_rate,
			row.billing_rule,
			row.machine,
			row.operation,
			(case when row.machine = %(machine)s then 2 else 0 end)
			+ (case when row.operation = %(operation)s then 1 else 0 end) as specificity
		from `tabCPC Contract Component` row
		inner join `tabCPC Contract` c on c.name = row.parent
		where {conditions}
		order by specificity desc, row.effective_from desc
		limit 1
		""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=True,
	)

	if not rows:
		frappe.throw(
			_("No effective CPC rate found for component {0} on {1}.").format(cpc_component, posting_date)
		)
	return rows[0]
