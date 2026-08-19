# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from tms.utils import stock as stock_utils


class TMSToolReceipt(Document):
	"""Receipt of tools into the Main Customer Location Warehouse (BRS section 14)."""

	def validate(self):
		self.set_warehouses()
		self.validate_items()

	def set_warehouses(self):
		warehouses = frappe.db.get_value(
			"TMS Customer Location", self.tms_location,
			["main_warehouse", "head_office_warehouse"], as_dict=True
		)
		self.target_warehouse = warehouses.main_warehouse

		if self.receipt_type in ("Head Office Transfer", "Reground Tool Return") and not self.source_warehouse:
			self.source_warehouse = warehouses.head_office_warehouse

		if self.source_warehouse and self.source_warehouse == self.target_warehouse:
			frappe.throw(_("Source and target warehouse cannot be the same."))

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

	def on_submit(self):
		purpose = "Material Transfer" if self.source_warehouse else "Material Receipt"
		self.stock_entry = stock_utils.make_transfer(
			self, self.items, self.source_warehouse, self.target_warehouse, purpose
		)
		self.db_set("stock_entry", self.stock_entry)

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Entry", "Stock Ledger Entry", "GL Entry")
		stock_utils.cancel_linked_stock_entry(self)
