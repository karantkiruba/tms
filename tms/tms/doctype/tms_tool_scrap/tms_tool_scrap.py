# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from tms.utils import stock as stock_utils
from tms.utils import validation as tms_validate
from tms.tms.doctype.tms_tool_registration.tms_tool_registration import get_condition_item


class TMSToolScrap(Document):
	"""Controlled scrapping of a tool (BRS section 25, rule 11).

	The tool is converted to its Scrap condition item, which is terminal, so it is
	permanently blocked from issue and from further regrinding.
	"""

	def validate(self):
		self.set_warehouse()
		self.validate_items()
		self.set_totals()

	def set_warehouse(self):
		if self.scrap_warehouse:
			return
		self.scrap_warehouse = frappe.db.get_value(
			"TMS Customer Location", self.tms_location, "used_tool_warehouse"
		)
		if not self.scrap_warehouse:
			frappe.throw(_("Set the warehouse holding the tools being scrapped."))

	def validate_items(self):
		if not self.items:
			frappe.throw(_("At least one item row is required."))

		for row in self.items:
			info = tms_validate.get_item_tool_info(row.item_code)
			if not info.get("tms_is_tool"):
				frappe.throw(
					_("Row {0}: {1} is not a registered TMS tool.").format(row.idx, row.item_code)
				)

			flags = tms_validate.get_condition_flags(info.get("tms_tool_condition"))
			if flags.get("is_terminal"):
				frappe.throw(
					_("Row {0}: {1} is already in a terminal condition.").format(row.idx, row.item_code)
				)

			row.scrap_item = get_condition_item(row.physical_tool_code, "SCR")
			row.current_regrind_count = tms_validate.get_serial_regrind_cycle(row.serial_no)

		stock_utils.validate_stock_available(self.items, self.scrap_warehouse)

	def set_totals(self):
		self.total_scrap_qty = sum(flt(r.qty) for r in self.items)
		self.total_scrap_value = sum(flt(r.scrap_value) for r in self.items)

	def on_submit(self):
		entries = []
		for row in self.items:
			entry = stock_utils.make_repack(
				self,
				[{"item_code": row.item_code, "qty": flt(row.qty), "serial_no": row.serial_no}],
				[{"item_code": row.scrap_item, "qty": flt(row.qty)}],
				self.scrap_warehouse,
			)
			entries.append(entry)

		self.db_set("stock_entry", entries[0] if entries else None)
		frappe.msgprint(
			_("{0} tool(s) scrapped. Stock converted to the Scrap condition and blocked "
			  "from further issue or regrinding.").format(len(entries)),
			indicator="orange", alert=True,
		)

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Entry", "Stock Ledger Entry", "GL Entry")
		for entry in frappe.get_all(
			"Stock Entry",
			filters={"tms_reference_doctype": self.doctype, "tms_reference_name": self.name,
			         "docstatus": 1},
			pluck="name",
		):
			se = frappe.get_doc("Stock Entry", entry)
			se.flags.ignore_permissions = True
			se.cancel()
