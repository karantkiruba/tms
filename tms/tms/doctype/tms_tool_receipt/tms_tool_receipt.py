# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from tms.utils import stock as stock_utils


class TMSToolReceipt(Document):
	"""Receipt of tools into the Main Customer Location Warehouse (BRS section 14).

	Tool cost is never entered here. Tools reach the company through a Purchase
	Receipt, in-house manufacture or a regrind completion, all of which set the
	valuation in the stock ledger. This transaction only moves that stock to the
	customer location, so the value carries itself.
	"""

	def validate(self):
		self.set_warehouses()
		self.validate_purchase_receipt()
		self.validate_items()
		self.set_incoming_rates()

	def set_warehouses(self):
		warehouses = frappe.db.get_value(
			"TMS Customer Location", self.tms_location,
			["main_warehouse", "head_office_warehouse"], as_dict=True
		)
		self.target_warehouse = warehouses.main_warehouse

		if not self.source_warehouse:
			if self.purchase_receipt:
				self.source_warehouse = frappe.db.get_value(
					"Purchase Receipt Item", {"parent": self.purchase_receipt}, "warehouse"
				)
			elif self.receipt_type in ("Head Office Transfer", "Reground Tool Return",
			                           "New Tool Supply"):
				self.source_warehouse = warehouses.head_office_warehouse

		if not self.source_warehouse:
			frappe.throw(
				_("Set a Source Warehouse, or a Head Office Receiving Warehouse on "
				  "TMS Customer Location {0}. Tools must already be in stock at their "
				  "purchase value before they are sent to the customer location.").format(
					self.tms_location
				),
				title=_("Source Warehouse Required"),
			)

		if self.source_warehouse == self.target_warehouse:
			frappe.throw(_("Source and target warehouse cannot be the same."))

	def validate_purchase_receipt(self):
		"""A referenced Purchase Receipt must actually cover the items being sent."""
		if not self.purchase_receipt:
			return

		if frappe.db.get_value("Purchase Receipt", self.purchase_receipt, "docstatus") != 1:
			frappe.throw(_("Purchase Receipt {0} is not submitted.").format(self.purchase_receipt))

		received = set(frappe.get_all(
			"Purchase Receipt Item",
			filters={"parent": self.purchase_receipt},
			pluck="item_code",
		))
		for row in self.items:
			if row.item_code not in received:
				frappe.throw(
					_("Row {0}: {1} does not appear on Purchase Receipt {2}.").format(
						row.idx, row.item_code, self.purchase_receipt
					)
				)

	def validate_items(self):
		if not self.items:
			frappe.throw(_("At least one item row is required."))

		for row in self.items:
			serialised = frappe.db.get_value("Item", row.item_code, "has_serial_no")
			if serialised and not row.serial_no:
				frappe.throw(
					_("Row {0}: {1} is serialised, so a serial number is required.").format(
						row.idx, row.item_code
					)
				)

		stock_utils.validate_stock_available(self.items, self.source_warehouse)

	def set_incoming_rates(self):
		"""Show the value being transferred, read from the source warehouse."""
		total = 0.0
		for row in self.items:
			row.rate = stock_utils.get_valuation_rate(row.item_code, self.source_warehouse)
			row.amount = flt(row.rate) * flt(row.qty)
			total += flt(row.amount)
		self.total_receipt_value = total

	def on_submit(self):
		self.stock_entry = stock_utils.make_transfer(
			self, self.items, self.source_warehouse, self.target_warehouse
		)
		self.db_set("stock_entry", self.stock_entry)

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Entry", "Stock Ledger Entry", "GL Entry")
		stock_utils.cancel_linked_stock_entry(self)
