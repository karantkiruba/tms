# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from tms.utils import stock as stock_utils


class TMSToolReturn(Document):
	"""Shopfloor to Used Tool Warehouse (BRS section 24).

	Rule 13: every removed tool returns to the Used Tool Warehouse first. The
	component history stays on the transaction even though the stock lands in a
	warehouse shared across components.
	"""

	def validate(self):
		self.set_warehouses()
		self.fetch_from_removal()
		self.validate_items()

	def set_warehouses(self):
		warehouses = frappe.db.get_value(
			"TMS Customer Location", self.tms_location,
			["shopfloor_warehouse", "used_tool_warehouse"], as_dict=True
		)
		self.source_warehouse = warehouses.shopfloor_warehouse
		self.target_warehouse = warehouses.used_tool_warehouse

	def fetch_from_removal(self):
		if not self.tool_removal:
			return

		removal = frappe.db.get_value(
			"TMS Tool Removal",
			self.tool_removal,
			["cpc_component", "machine", "operation", "item_code", "serial_no",
			 "actual_tool_life", "regrind_cycle", "removal_reason", "docstatus"],
			as_dict=True,
		)
		if removal.docstatus != 1:
			frappe.throw(_("Tool Removal {0} is not submitted.").format(self.tool_removal))

		self.cpc_component = removal.cpc_component
		self.machine = removal.machine
		self.operation = removal.operation

		for row in self.items:
			if row.item_code != removal.item_code:
				continue
			row.serial_no = row.serial_no or removal.serial_no
			row.actual_tool_life = removal.actual_tool_life
			row.regrind_cycle = removal.regrind_cycle
			row.removal_reason = removal.removal_reason

	def validate_items(self):
		if not self.items:
			frappe.throw(_("At least one item row is required."))
		stock_utils.validate_stock_available(self.items, self.source_warehouse)

	def on_submit(self):
		self.stock_entry = stock_utils.make_transfer(
			self, self.items, self.source_warehouse, self.target_warehouse
		)
		self.db_set("stock_entry", self.stock_entry)

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Entry", "Stock Ledger Entry", "GL Entry")
		stock_utils.cancel_linked_stock_entry(self)
