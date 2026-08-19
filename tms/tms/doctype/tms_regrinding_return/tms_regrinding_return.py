# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from tms.utils import stock as stock_utils
from tms.utils import validation as tms_validate


class TMSRegrindingReturn(Document):
	"""Return of regrindable tools from the customer site to Head Office (BRS section 26).

	Rule 10: regrindable tools leave the customer location through a controlled
	transaction. A Regrind Cycle is opened for each row so the tool's cycle can be
	tracked from here through to the reground item coming back.
	"""

	def validate(self):
		self.set_warehouses()
		self.validate_items()

	def set_warehouses(self):
		warehouses = frappe.db.get_value(
			"TMS Customer Location", self.tms_location,
			["used_tool_warehouse", "head_office_warehouse"], as_dict=True
		)
		self.source_warehouse = warehouses.used_tool_warehouse
		if not self.target_warehouse:
			self.target_warehouse = warehouses.head_office_warehouse

		if not self.target_warehouse:
			frappe.throw(
				_("Set a Head Office Receiving Warehouse on TMS Customer Location {0}, "
				  "or choose one on this document.").format(self.tms_location)
			)

		if self.source_warehouse == self.target_warehouse:
			frappe.throw(_("Source and target warehouse cannot be the same."))

	def validate_items(self):
		if not self.items:
			frappe.throw(_("At least one item row is required."))

		for row in self.items:
			tms_validate.validate_regrind_capacity(row.item_code, row.serial_no)

			row.current_regrind_count = tms_validate.get_serial_regrind_cycle(row.serial_no)
			row.max_regrind_count = frappe.db.get_value(
				"TMS Tool Type", row.tool_type, "max_regrind_count"
			) or 0

		stock_utils.validate_stock_available(self.items, self.source_warehouse)

	def on_submit(self):
		self.stock_entry = stock_utils.make_transfer(
			self, self.items, self.source_warehouse, self.target_warehouse
		)
		self.db_set("stock_entry", self.stock_entry)
		self.open_regrind_cycles()

	def open_regrind_cycles(self):
		"""One cycle record per returned tool, ready for the RGP conversion."""
		created = []
		for row in self.items:
			cycle = frappe.new_doc("TMS Regrind Cycle")
			cycle.update({
				"company": self.company,
				"customer": self.customer,
				"tms_location": self.tms_location,
				"regrinding_return": self.name,
				"physical_tool_code": row.physical_tool_code,
				"tool_type": row.tool_type,
				"source_item": row.item_code,
				"source_serial_no": row.serial_no,
				"ho_warehouse": self.target_warehouse,
				"cpc_component_last_used": row.cpc_component_last_used,
				"qty": row.qty,
			})
			cycle.insert(ignore_permissions=True)
			row.db_set("regrind_cycle", cycle.name)
			created.append(cycle.name)

		if created:
			frappe.msgprint(
				_("Regrind Cycle(s) opened: {0}").format(", ".join(created)),
				indicator="green", alert=True
			)
		return created

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Entry", "Stock Ledger Entry", "GL Entry")
		for row in self.items:
			if row.regrind_cycle and frappe.db.exists("TMS Regrind Cycle", row.regrind_cycle):
				cycle = frappe.get_doc("TMS Regrind Cycle", row.regrind_cycle)
				if cycle.docstatus == 1:
					frappe.throw(
						_("Regrind Cycle {0} is already in process. Cancel it first.").format(cycle.name)
					)
				frappe.delete_doc("TMS Regrind Cycle", cycle.name, force=True,
				                  ignore_permissions=True)
		stock_utils.cancel_linked_stock_entry(self)
