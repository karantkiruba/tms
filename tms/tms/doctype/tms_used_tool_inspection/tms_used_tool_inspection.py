# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from tms.utils import stock as stock_utils
from tms.utils import validation as tms_validate
from tms.tms.doctype.tms_tool_registration.tms_tool_registration import get_condition_item

class TMSUsedToolInspection(Document):
	"""Inspection and disposition of used tools (BRS section 25).

	Reusable tools move straight back to the Main Customer Location Warehouse.
	Regrind and Scrap rows are recorded here and consumed by the regrinding and
	scrap transactions, so the stock stays in the Used Tool Warehouse until then.
	"""

	def validate(self):
		#self.set_warehouses()
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
			#row.current_regrind_count = tms_validate.get_serial_regrind_cycle(row.serial_no)
			row.max_regrind_count = frappe.db.get_value(
				"TMS Tool Registration", info.get("custom_tms_tool_registration"), "max_regrind_count"
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
		regrind = [row for row in self.items if row.disposition == "Regrind"]
		scrap = [row for row in self.items if row.disposition == "Scrap"]
		if reusable:
			self.stock_entry = stock_utils.make_transfer(
				self, reusable, self.used_tool_warehouse, self.main_warehouse
			)
			self.db_set("stock_entry", self.stock_entry)
		if regrind:
			self.convert_regrind_to_rgp(regrind)
			self.db_set("regrind_stock_entry", self.regrind_stock_entry)

		if scrap:
			self.scrap_stock_entry = self.convert_scrap_to_scrap_item(scrap)
			self.db_set("scrap_stock_entry", self.scrap_stock_entry)

		self.db_set("disposition_summary", self.build_summary())

	def build_summary(self):
		counts = {}
		for row in self.items:
			counts[row.disposition] = counts.get(row.disposition, 0) + 1
		return ", ".join("{0}: {1}".format(k, v) for k, v in sorted(counts.items()))

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Entry", "Stock Ledger Entry", "GL Entry")
		#stock_utils.cancel_linked_stock_entry(self)
		for field in (
			"stock_entry",
			"regrind_stock_entry",
			"scrap_stock_entry"
		):
			entry = self.get(field)

			if entry and frappe.db.exists("Stock Entry", entry):
				stock_entry = frappe.get_doc("Stock Entry", entry)

				if stock_entry.docstatus == 1:
					stock_entry.flags.ignore_permissions = True
					stock_entry.cancel()

	def convert_regrind_to_rgp(self, rows):
		"""Convert inspected Regrind tools into Regrinding Pending stock."""

		for row in rows:
			info = tms_validate.get_item_tool_info(row.item_code)

			rgp_item = frappe.db.get_value(
				"TMS Registered Tool Item",
				{
					"parent": info.get("custom_tms_tool_registration"),
					"condition_name": "Regrinding Pending"
				},
				"item_code"
			)

			if not rgp_item:
				frappe.throw(
					_("No RGP condition item found for {0}.").format(
						row.item_code
					)
				)

			consume = [{
				"item_code": row.item_code,
				"qty": row.qty,
				"serial_no": row.serial_no
			}]

			produce = [{
				"item_code": rgp_item,
				"qty": row.qty
			}]

			self.regrind_stock_entry = stock_utils.make_repack(
				self,
				consume,
				produce,
				self.used_tool_warehouse
			)


	def convert_scrap_to_scrap_item(self, rows):
		"""Convert inspected Scrap tools into Scrap condition items."""

		stock_entries = []

		for row in rows:
			scrap_item = get_condition_item(row.physical_tool_code, "SCR")

			if not scrap_item:
				frappe.throw(
					_("No Scrap condition item found for {0}.").format(
						row.item_code
					)
				)

			consume = [{
				"item_code": row.item_code,
				"qty": row.qty,
				"serial_no": row.serial_no
			}]

			produce = [{
				"item_code": scrap_item,
				"qty": row.qty
			}]

			entry = stock_utils.make_repack(
				self,
				consume,
				produce,
				self.used_tool_warehouse
			)

			stock_entries.append(entry)

		return ", ".join(stock_entries)
