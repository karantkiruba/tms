# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from tms.utils import validation as tms_validate


class TMSCPCBillingStatement(Document):
	"""CPC Billing Statement (BRS sections 34 to 37).

	Billing value is confirmed quantity times the effective-dated CPC rate.
	Every row points at the exact Production Declaration line it bills, and that
	line's billed quantity is updated on submit, so production cannot be billed
	twice (rule 20).
	"""

	def validate(self):
		tms_validate.validate_active_contract(self.cpc_contract, None, self.posting_date)
		self.validate_rows()
		self.set_totals()
		self.set_tool_issue_comparison()

	def validate_rows(self):
		if not self.items:
			frappe.throw(_("At least one billing row is required."))

		seen = set()
		for row in self.items:
			if row.declaration_item in seen:
				frappe.throw(
					_("Row {0}: production line {1} appears more than once on this statement.").format(
						row.idx, row.declaration_item
					)
				)
			seen.add(row.declaration_item)

			source = frappe.db.get_value(
				"TMS Production Declaration Item",
				row.declaration_item,
				["parent", "billable_qty", "billed_qty", "cpc_component", "docstatus"],
				as_dict=True,
			)
			if not source:
				frappe.throw(_("Row {0}: production line no longer exists.").format(row.idx))

			if source.parent != row.production_declaration:
				frappe.throw(
					_("Row {0}: production line does not belong to {1}.").format(
						row.idx, row.production_declaration
					)
				)

			row.customer_confirmed_qty = flt(source.billable_qty)
			row.previously_billed_qty = flt(source.billed_qty)
			available = flt(source.billable_qty) - flt(source.billed_qty)
			row.remaining_unbilled_qty = available - flt(row.current_billing_qty)

			if flt(row.current_billing_qty) <= 0:
				frappe.throw(_("Row {0}: Current Billing Quantity must be greater than zero.").format(row.idx))

			if flt(row.current_billing_qty) > available:
				frappe.throw(
					_("Row {0}: only {1} remains unbilled on {2}, but {3} is being billed.").format(
						row.idx, available, row.production_declaration, row.current_billing_qty
					),
					title=_("Over Billing"),
				)

			row.billing_value = flt(row.current_billing_qty) * flt(row.cpc_rate)

	def set_totals(self):
		self.total_billing_qty = sum(flt(r.current_billing_qty) for r in self.items)
		self.total_billing_value = sum(flt(r.billing_value) for r in self.items)

	def set_tool_issue_comparison(self):
		"""Tool issue value against CPC billing for the same components and period."""
		components = list({r.cpc_component for r in self.items})
		if not components:
			return

		value = frappe.db.sql(
			"""
			select coalesce(sum(item.issue_value), 0)
			from `tabTMS Tool Issue Item` item
			inner join `tabTMS Tool Issue` issue on issue.name = item.parent
			where issue.docstatus = 1
			  and issue.cpc_component in %(components)s
			  and issue.posting_date between %(from_date)s and %(to_date)s
			""",
			{"components": components, "from_date": self.from_date, "to_date": self.to_date},
		)[0][0]

		self.total_tool_issue_value = flt(value)
		if flt(self.total_billing_qty):
			self.tool_issue_value_per_component = flt(value) / flt(self.total_billing_qty)
		else:
			self.tool_issue_value_per_component = 0
		self.contribution_value = flt(self.total_billing_value) - flt(value)

	@frappe.whitelist()
	def fetch_unbilled_production(self):
		"""Pull every unbilled confirmed production line for the contract and period."""
		if not (self.cpc_contract and self.from_date and self.to_date):
			frappe.throw(_("Set the CPC Contract and the billing period first."))

		rows = frappe.db.sql(
			"""
			select
				item.name as declaration_item,
				item.parent as production_declaration,
				item.cpc_component, item.machine, item.production_date,
				item.billable_qty, item.billed_qty, item.cpc_rate
			from `tabTMS Production Declaration Item` item
			inner join `tabTMS Production Declaration` decl on decl.name = item.parent
			where decl.docstatus = 1
			  and decl.cpc_contract = %(contract)s
			  and decl.confirmation_status = 'Confirmed'
			  and item.production_date between %(from_date)s and %(to_date)s
			  and (item.billable_qty - item.billed_qty) > 0
			order by item.production_date, item.cpc_component
			""",
			{"contract": self.cpc_contract, "from_date": self.from_date, "to_date": self.to_date},
			as_dict=True,
		)

		self.set("items", [])
		for row in rows:
			self.append("items", {
				"declaration_item": row.declaration_item,
				"production_declaration": row.production_declaration,
				"cpc_component": row.cpc_component,
				"machine": row.machine,
				"production_date": row.production_date,
				"customer_confirmed_qty": row.billable_qty,
				"previously_billed_qty": row.billed_qty,
				"current_billing_qty": flt(row.billable_qty) - flt(row.billed_qty),
				"cpc_rate": row.cpc_rate,
			})

		return len(rows)

	def on_submit(self):
		self.update_declaration_lines(direction=1)
		self.db_set("billing_status", "Approved")

	def on_cancel(self):
		if self.sales_invoice and frappe.db.get_value("Sales Invoice", self.sales_invoice, "docstatus") == 1:
			frappe.throw(
				_("Sales Invoice {0} is still submitted. Cancel it before cancelling this statement.").format(
					self.sales_invoice
				)
			)
		self.update_declaration_lines(direction=-1)
		self.db_set("billing_status", "Cancelled")

	def update_declaration_lines(self, direction):
		"""Move billed quantity on the source production lines and restate their status."""
		for row in self.items:
			source = frappe.db.get_value(
				"TMS Production Declaration Item", row.declaration_item,
				["billed_qty", "billable_qty"], as_dict=True
			)
			billed = flt(source.billed_qty) + direction * flt(row.current_billing_qty)
			billed = max(billed, 0)

			if billed <= 0:
				status = "Unbilled"
			elif billed >= flt(source.billable_qty):
				status = "Fully Billed"
			else:
				status = "Partially Billed"

			frappe.db.set_value(
				"TMS Production Declaration Item", row.declaration_item,
				{
					"billed_qty": billed,
					"unbilled_qty": flt(source.billable_qty) - billed,
					"billing_status": status,
				},
				update_modified=False,
			)

	@frappe.whitelist()
	def make_sales_invoice(self):
		"""Create the standard ERPNext Sales Invoice for an approved statement."""
		if self.docstatus != 1:
			frappe.throw(_("Approve the billing statement before invoicing."))
		if self.sales_invoice:
			frappe.throw(_("Sales Invoice {0} already exists for this statement.").format(self.sales_invoice))

		contract = frappe.get_cached_doc("CPC Contract", self.cpc_contract)
		default_item = frappe.db.get_single_value("TMS Settings", "default_cpc_billing_item")

		si = frappe.new_doc("Sales Invoice")
		si.customer = self.customer
		si.company = self.company
		si.currency = self.currency
		si.posting_date = self.posting_date
		si.po_no = self.customer_po
		si.tms_cpc_contract = self.cpc_contract
		si.tms_billing_statement = self.name
		si.tms_location = self.tms_location
		si.tms_billing_period = "{0} to {1}".format(self.from_date, self.to_date)

		if contract.payment_terms:
			si.payment_terms_template = contract.payment_terms
		if contract.tax_template:
			si.taxes_and_charges = contract.tax_template
		if contract.cost_center:
			si.cost_center = contract.cost_center

		for component, rows in self.group_by_component().items():
			billing_item = frappe.db.get_value("CPC Component", component, "billing_item") or default_item
			if not billing_item:
				frappe.throw(
					_("No billing item set for CPC Component {0}, and no default in TMS Settings.").format(
						component
					)
				)

			qty = sum(flt(r.current_billing_qty) for r in rows)
			value = sum(flt(r.billing_value) for r in rows)
			si.append("items", {
				"item_code": billing_item,
				"qty": qty,
				"rate": flt(value) / qty if qty else 0,
				"description": _("CPC billing for {0}, {1} to {2}").format(
					component, self.from_date, self.to_date
				),
				"cost_center": contract.cost_center,
				"tms_cpc_component": component,
			})

		si.insert(ignore_permissions=True)

		self.db_set("sales_invoice", si.name)
		self.db_set("billing_status", "Invoiced")
		return si.name

	def group_by_component(self):
		grouped = {}
		for row in self.items:
			grouped.setdefault(row.cpc_component, []).append(row)
		return grouped
