# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from tms.utils import stock as stock_utils
from tms.utils import validation as tms_validate


class TMSUsedToolInspection(Document):
	"""Inspection and disposition of used tools (BRS section 25).

	Reusable tools move straight back to the Main Customer Location Warehouse.
	Regrind and Scrap rows are recorded here and consumed by the regrinding and
	scrap transactions, so the stock stays in the Used Tool Warehouse until then.
	"""

	def validate(self):
		self.set_warehouses()
		self.validate_items()

	def set_warehouses(self):
		warehouses = frappe.db.get_value(
			"TMS Customer Location", self.tms_location,
			["main_warehouse", "used_tool_warehouse"], as_dict=True
		)
		self.main_warehouse = warehouses.main_warehouse
		self.used_tool_warehouse = warehouses.used_tool_warehouse

	def validate_items(self):
		if not self.items:
			frappe.throw(_("At least one item row is required."))

		for row in self.items:
			info = tms_validate.get_item_tool_info(row.item_code)
			row.current_regrind_count = tms_validate.get_serial_regrind_cycle(row.serial_no)
			row.max_regrind_count = frappe.db.get_value(
				"TMS Tool Type", info.get("tms_tool_type"), "max_regrind_count"
			) or 0

			if row.disposition == "Regrind":
				tms_validate.validate_regrind_capacity(row.item_code, row.serial_no)

			if row.disposition == "Reusable":
				flags = tms_validate.get_condition_flags(info.get("tms_tool_condition"))
				if flags.get("is_terminal"):
					frappe.throw(
						_("Row {0}: {1} is in a terminal condition and cannot be marked Reusable.").format(
							row.idx, row.item_code
						)
					)

		stock_utils.validate_stock_available(self.items, self.used_tool_warehouse)

	def on_submit(self):
		reusable = [row for row in self.items if row.disposition == "Reusable"]
		if reusable:
			self.stock_entry = stock_utils.make_transfer(
				self, reusable, self.used_tool_warehouse, self.main_warehouse
			)
			self.db_set("stock_entry", self.stock_entry)

		self.db_set("disposition_summary", self.build_summary())

	def build_summary(self):
		counts = {}
		for row in self.items:
			counts[row.disposition] = counts.get(row.disposition, 0) + 1
		return ", ".join("{0}: {1}".format(k, v) for k, v in sorted(counts.items()))

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Entry", "Stock Ledger Entry", "GL Entry")
		stock_utils.cancel_linked_stock_entry(self)
