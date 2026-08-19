# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

WAREHOUSE_ROLES = (
	("main_warehouse", "Main"),
	("shopfloor_warehouse", "Shopfloor"),
	("used_tool_warehouse", "Used Tool"),
)


class TMSStockReconciliation(Document):
	"""Physical verification across the three TMS warehouses (BRS section 43).

	TMS records the count and the reason for each variance. The approved
	adjustment is posted by the standard ERPNext Stock Reconciliation, which
	stays the source of truth for inventory.
	"""

	def validate(self):
		self.calculate_variance()

	def calculate_variance(self):
		total_value = 0.0
		lines_with_variance = 0

		for row in self.items:
			row.variance = flt(row.physical_qty) - flt(row.system_qty)
			row.variance_value = flt(row.variance) * flt(row.valuation_rate)

			if row.variance:
				lines_with_variance += 1
				total_value += flt(row.variance_value)
				if not row.variance_reason:
					frappe.throw(
						_("Row {0}: a variance reason is required for {1} in {2}.").format(
							row.idx, row.item_code, row.warehouse
						)
					)

		self.lines_with_variance = lines_with_variance
		self.total_variance_value = total_value

	@frappe.whitelist()
	def fetch_stock(self):
		"""Pull the current system position for every TMS warehouse at this location."""
		warehouses = self.get_warehouses()
		if not warehouses:
			frappe.throw(_("No TMS warehouses are configured on {0}.").format(self.tms_location))

		rows = frappe.db.sql(
			"""
			select b.item_code, b.warehouse, b.actual_qty, b.valuation_rate
			from tabBin b
			inner join tabItem i on i.name = b.item_code
			where b.warehouse in %(warehouses)s and b.actual_qty != 0
			order by b.warehouse, b.item_code
			""",
			{"warehouses": list(warehouses)}, as_dict=True,
		)

		self.set("items", [])
		for row in rows:
			self.append("items", {
				"item_code": row.item_code,
				"warehouse": row.warehouse,
				"warehouse_role": warehouses[row.warehouse],
				"system_qty": row.actual_qty,
				"physical_qty": row.actual_qty,
				"valuation_rate": row.valuation_rate,
			})

		return len(rows)

	def get_warehouses(self):
		location = frappe.get_cached_doc("TMS Customer Location", self.tms_location)
		selected = {}
		for field, label in WAREHOUSE_ROLES:
			include = self.get("include_" + field)
			if include and location.get(field):
				selected[location.get(field)] = label
		return selected

	def on_submit(self):
		self.create_stock_reconciliation()

	def create_stock_reconciliation(self):
		"""Post the approved adjustment through the standard ERPNext transaction."""
		variance_rows = [r for r in self.items if flt(r.variance)]
		if not variance_rows:
			self.db_set("status", "No Variance")
			frappe.msgprint(_("No variance found. No stock adjustment was needed."),
			                indicator="green", alert=True)
			return

		sr = frappe.new_doc("Stock Reconciliation")
		sr.company = self.company
		sr.purpose = "Stock Reconciliation"
		sr.posting_date = self.posting_date
		sr.set_posting_time = 1
		sr.tms_reference_doctype = self.doctype
		sr.tms_reference_name = self.name
		sr.tms_location = self.tms_location

		for row in variance_rows:
			sr.append("items", {
				"item_code": row.item_code,
				"warehouse": row.warehouse,
				"qty": flt(row.physical_qty),
				"valuation_rate": flt(row.valuation_rate),
			})

		sr.insert(ignore_permissions=True)
		sr.submit()

		self.db_set("stock_reconciliation", sr.name)
		self.db_set("status", "Adjusted")

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Reconciliation", "Stock Ledger Entry", "GL Entry")
		if self.stock_reconciliation and frappe.db.exists(
			"Stock Reconciliation", self.stock_reconciliation
		):
			sr = frappe.get_doc("Stock Reconciliation", self.stock_reconciliation)
			if sr.docstatus == 1:
				sr.flags.ignore_permissions = True
				sr.cancel()
		self.db_set("status", "Cancelled")
