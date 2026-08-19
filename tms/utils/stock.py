# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt
"""Stock posting helpers.

Standard ERPNext Stock Entries remain the source of truth for inventory
(BRS rule 28). TMS documents own the business control and traceability, and
delegate every physical movement to a Stock Entry linked back to the TMS
document that raised it.
"""

import frappe
from frappe import _
from frappe.utils import flt


def make_transfer(doc, rows, source_warehouse, target_warehouse, purpose="Material Transfer"):
	"""Create and submit a Stock Entry for a TMS document.

	`rows` are child rows carrying item_code, qty and optionally serial_no.
	Returns the submitted Stock Entry name.
	"""
	if not rows:
		frappe.throw(_("No items to post."))

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = purpose
	se.purpose = purpose
	se.company = doc.company
	se.posting_date = doc.posting_date
	se.set_posting_time = 1
	if getattr(doc, "posting_time", None):
		se.posting_time = doc.posting_time

	se.tms_reference_doctype = doc.doctype
	se.tms_reference_name = doc.name
	se.tms_location = getattr(doc, "tms_location", None)
	se.tms_cpc_component = getattr(doc, "cpc_component", None)

	for row in rows:
		item = {
			"item_code": row.item_code,
			"qty": flt(row.qty),
			"uom": row.uom or frappe.db.get_value("Item", row.item_code, "stock_uom"),
			"conversion_factor": 1,
		}
		if purpose in ("Material Transfer", "Material Issue"):
			item["s_warehouse"] = source_warehouse
		if purpose in ("Material Transfer", "Material Receipt"):
			item["t_warehouse"] = target_warehouse

		if flt(getattr(row, "rate", 0)):
			item["basic_rate"] = flt(row.rate)
			item["allow_zero_valuation_rate"] = 0

		if getattr(row, "serial_no", None):
			item["use_serial_batch_fields"] = 1
			item["serial_no"] = row.serial_no

		se.append("items", item)

	se.insert(ignore_permissions=True)
	se.submit()

	_write_back_rates(se, rows)
	return se.name


def _write_back_rates(se, rows):
	"""Copy the valuation actually applied by the Stock Entry onto the TMS rows.

	Issue value is measured at the rate the stock ledger used, not at a standard
	cost, so BRS section 37 reconciles against real inventory valuation.
	"""
	by_item = {}
	for se_row in se.items:
		by_item.setdefault(se_row.item_code, []).append(se_row)

	for row in rows:
		candidates = by_item.get(row.item_code)
		if not candidates:
			continue
		se_row = candidates.pop(0)
		if not hasattr(row, "valuation_rate"):
			continue

		# valuation_rate carries basic_rate plus any additional cost, so a reground
		# tool is issued at material cost plus its regrinding charge.
		rate = flt(se_row.valuation_rate) or flt(se_row.basic_rate)
		row.db_set("valuation_rate", rate, update_modified=False)
		if hasattr(row, "issue_value"):
			row.db_set("issue_value", rate * flt(row.qty), update_modified=False)


def cancel_linked_stock_entry(doc):
	"""Cancel the Stock Entry raised by a TMS document."""
	if not getattr(doc, "stock_entry", None):
		return
	if not frappe.db.exists("Stock Entry", doc.stock_entry):
		return

	se = frappe.get_doc("Stock Entry", doc.stock_entry)
	if se.docstatus == 1:
		se.flags.ignore_permissions = True
		se.cancel()


def get_available_qty(item_code, warehouse):
	return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse},
	                               "actual_qty"))


def validate_stock_available(rows, warehouse):
	"""Block a movement that the source warehouse cannot cover."""
	required = {}
	for row in rows:
		required[row.item_code] = required.get(row.item_code, 0) + flt(row.qty)

	for item_code, qty in required.items():
		available = get_available_qty(item_code, warehouse)
		if available < qty:
			frappe.throw(
				_("Insufficient stock for {0} in {1}. Required {2}, available {3}.").format(
					item_code, warehouse, qty, available
				),
				title=_("Insufficient Stock"),
			)


def make_repack(doc, consume_rows, produce_rows, warehouse, additional_cost=0,
                cost_description=None):
	"""Convert one tool condition into another (BRS sections 27 and 29).

	A Repack consumes the incoming condition item and produces the outgoing one,
	so the tool keeps its stock value across the conversion. Regrinding charges
	are added as an additional cost, which is what lifts the reground tool's
	valuation above the pending one.
	"""
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Repack"
	se.purpose = "Repack"
	se.company = doc.company
	se.posting_date = doc.posting_date
	se.set_posting_time = 1

	se.tms_reference_doctype = doc.doctype
	se.tms_reference_name = doc.name
	se.tms_location = getattr(doc, "tms_location", None)
	se.tms_cpc_component = getattr(doc, "cpc_component_last_used", None)

	for row in consume_rows:
		item = {
			"item_code": row["item_code"],
			"qty": flt(row["qty"]),
			"s_warehouse": warehouse,
			"uom": frappe.db.get_value("Item", row["item_code"], "stock_uom"),
			"conversion_factor": 1,
			# ERPNext forces the finished-good rate to zero when this flag is set,
			# which would throw away the tool's value across the conversion.
			"allow_zero_valuation_rate": 0,
		}
		if row.get("serial_no"):
			item["use_serial_batch_fields"] = 1
			item["serial_no"] = row["serial_no"]
		se.append("items", item)

	for row in produce_rows:
		item = {
			"item_code": row["item_code"],
			"qty": flt(row["qty"]),
			"t_warehouse": warehouse,
			"uom": frappe.db.get_value("Item", row["item_code"], "stock_uom"),
			"conversion_factor": 1,
			"is_finished_item": 1,
			"allow_zero_valuation_rate": 0,
		}
		if row.get("serial_no"):
			item["use_serial_batch_fields"] = 1
			item["serial_no"] = row["serial_no"]
		se.append("items", item)

	if flt(additional_cost):
		se.append("additional_costs", {
			"expense_account": get_regrind_expense_account(doc.company),
			"description": cost_description or _("Regrinding Charges"),
			"amount": flt(additional_cost),
		})

	se.insert(ignore_permissions=True)
	se.submit()
	return se.name


def generate_serial_no(item_code):
	"""Next serial for an item from its own series."""
	from frappe.model.naming import make_autoname

	series = frappe.db.get_value("Item", item_code, "serial_no_series")
	if not series:
		frappe.throw(_("Item {0} has no Serial No Series configured.").format(item_code))
	return make_autoname(series)


def get_regrind_expense_account(company):
	"""Account the regrinding charge is booked to before it lands in valuation."""
	account = frappe.db.get_single_value("TMS Settings", "regrind_expense_account")
	if account:
		return account

	for field in ("expenses_included_in_valuation", "default_expense_account"):
		account = frappe.db.get_value("Company", company, field)
		if account:
			return account

	frappe.throw(
		_("Set a Regrinding Expense Account in TMS Settings, or a default expense account "
		  "on company {0}.").format(company)
	)
