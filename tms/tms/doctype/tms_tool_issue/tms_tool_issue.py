# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from tms.utils import stock as stock_utils
from tms.utils import validation as tms_validate


class TMSToolIssue(Document):
	"""Component-wise tool issue, Main Warehouse to Shopfloor (BRS section 15).

	CPC Component, machine and operation are mandatory because the warehouse
	records where the tool is while the transaction records what it is used for
	(BRS section 6).
	"""

	def validate(self):
		#self.set_warehouses()
		tms_validate.validate_active_contract(self.cpc_contract, self.cpc_component, self.posting_date)
		tms_validate.validate_machine_operation(self.cpc_component, self.machine, self.operation)
		self.validate_items()
		self.set_totals()

	#def set_warehouses(self):
		#warehouses = frappe.db.get_value(
		#	"TMS Customer Location", self.tms_location,
		#	["main_warehouse", "shopfloor_warehouse"], as_dict=True
		#)
		#self.source_warehouse = warehouses.main_warehouse
		#self.target_warehouse = warehouses.shopfloor_warehouse

	def validate_items(self):
		if not self.items:
			frappe.throw(_("At least one tool row is required."))

		pfep = tms_validate.get_pfep_plan(self.cpc_component, self.posting_date)
		self.pfep = pfep.name if pfep else None

		primary_rows = []
		for row in self.items:
			info = tms_validate.validate_issuable(row.item_code)

			if info.get("has_serial_no") and not row.serial_no:
				frappe.throw(
					_("Row {0}: {1} is serialised, so a serial number is required.").format(
						row.idx, row.item_code
					)
				)

			row.regrind_cycle = tms_validate.get_serial_regrind_cycle(row.serial_no)

			standard_qty, pfep_row = tms_validate.get_pfep_standard_qty(
				pfep, info.get("custom_tms_tool_registration"), self.machine, self.operation
			)
			row.pfep_standard_qty = standard_qty
			row.additional_qty = max(flt(row.qty) - flt(standard_qty), 0)

			if pfep_row:
				flags = tms_validate.get_condition_flags(info.get("tms_tool_condition"))
				row.planned_tool_life = (
					pfep_row.planned_reground_tool_life
					if flags.get("is_regrind_output")
					else pfep_row.planned_new_tool_life
				)
				if pfep_row.is_primary_tool:
					row.is_primary_tool = 1

			if row.is_primary_tool:
				primary_rows.append(row.idx)

		if len(primary_rows) > 1:
			frappe.msgprint(
				_("Rows {0} are all marked as the primary tool. Only one primary tool may be "
				  "issued per machine and operation.").format(", ".join(str(r) for r in primary_rows))
			)

		stock_utils.validate_stock_available(self.items, self.source_warehouse)

	def set_totals(self):
		self.total_issue_value = sum(flt(row.issue_value) for row in self.items)
		self.total_additional_qty = sum(flt(row.additional_qty) for row in self.items)

	def before_submit(self):
		if self.is_additional_issue and not self.additional_reason:
			frappe.throw(_("A reason is required for an additional tool issue."))

	def on_submit(self):
		self.stock_entry = stock_utils.make_transfer(
			self, self.items, self.source_warehouse, self.target_warehouse
		)
		self.db_set("stock_entry", self.stock_entry)
		self.reload()
		self.db_set("total_issue_value", sum(flt(row.issue_value) for row in self.items))

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Entry", "Stock Ledger Entry", "GL Entry")
		stock_utils.cancel_linked_stock_entry(self)
