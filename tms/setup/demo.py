# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt
"""Smoke test fixtures for the TMS foundation.

Everything created here is prefixed TMSDEMO- so it is unambiguous and can be
removed in one call. This exercises the core design rule: one physical tool is
one item code per condition, with the reground item serialised so its serial
carries the regrind cycle.
"""

import frappe
from frappe.utils import flt

DEMO_PREFIX = "TMSDEMO-"
DEMO_TOOL = DEMO_PREFIX + "T0001"
DEMO_TOOL_TYPE = DEMO_PREFIX + "DRILL12"
DEMO_CATEGORY = DEMO_PREFIX + "DRILL"


def run_smoke_test(company=None, item_group="Consumable", stock_uom="Nos"):
	company = company or frappe.db.get_value("Company", {}, "name")

	_ensure_category()
	_ensure_tool_type()
	registration = _register_tool(company, item_group, stock_uom)

	result = {
		"registration": registration.name,
		"registration_status": registration.registration_status,
		"items": [],
	}

	for row in registration.conditions:
		item = frappe.db.get_value(
			"Item",
			row.item_code,
			["item_code", "has_serial_no", "serial_no_series", "tms_tool_condition",
			 "tms_physical_tool_code", "tms_tool_type"],
			as_dict=True,
		)
		result["items"].append(item)

	return result


def _ensure_category():
	if not frappe.db.exists("TMS Tool Category", DEMO_CATEGORY):
		doc = frappe.new_doc("TMS Tool Category")
		doc.category_name = DEMO_CATEGORY
		doc.insert(ignore_permissions=True)


def _ensure_tool_type():
	if frappe.db.exists("TMS Tool Type", DEMO_TOOL_TYPE):
		return
	doc = frappe.new_doc("TMS Tool Type")
	doc.update(
		{
			"tool_type_code": DEMO_TOOL_TYPE,
			"tool_type_name": "Demo Carbide Drill 12mm",
			"tool_category": DEMO_CATEGORY,
			"is_regrindable": 1,
			"max_regrind_count": 5,
			"planned_new_tool_life": 5000,
			"planned_reground_tool_life": 4000,
			"standard_new_tool_cost": 15000,
			"standard_regrind_cost": 2500,
			"default_uom": "Nos",
		}
	)
	doc.insert(ignore_permissions=True)


def _register_tool(company, item_group, stock_uom):
	existing = frappe.db.exists(
		"TMS Tool Registration", {"physical_tool_code": DEMO_TOOL, "docstatus": 1}
	)
	if existing:
		return frappe.get_doc("TMS Tool Registration", existing)

	doc = frappe.new_doc("TMS Tool Registration")
	doc.update(
		{
			"physical_tool_code": DEMO_TOOL,
			"tool_type": DEMO_TOOL_TYPE,
			"tool_description": "Demo Carbide Drill 12mm",
			"company": company,
			"item_group": item_group,
			"stock_uom": stock_uom,
			"gst_hsn_code": DEMO_HSN,
		}
	)
	doc.fetch_conditions()
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def cleanup():
	"""Remove everything the smoke test created."""
	removed = []

	for registration in frappe.get_all(
		"TMS Tool Registration", filters={"physical_tool_code": ("like", DEMO_PREFIX + "%")}
	):
		doc = frappe.get_doc("TMS Tool Registration", registration.name)
		if doc.docstatus == 1:
			doc.cancel()
		frappe.delete_doc("TMS Tool Registration", doc.name, force=True, ignore_permissions=True)
		removed.append(doc.name)

	for item in frappe.get_all("Item", filters={"item_code": ("like", DEMO_PREFIX + "%")}):
		frappe.delete_doc("Item", item.name, force=True, ignore_permissions=True)
		removed.append(item.name)

	for doctype, field in (("TMS Tool Type", "name"), ("TMS Tool Category", "name")):
		for row in frappe.get_all(doctype, filters={field: ("like", DEMO_PREFIX + "%")}):
			frappe.delete_doc(doctype, row.name, force=True, ignore_permissions=True)
			removed.append(row.name)

	frappe.db.commit()
	return removed


# --------------------------------------------------------------- P1 flow test

DEMO_CUSTOMER = DEMO_PREFIX + "Customer"
DEMO_LOCATION = DEMO_PREFIX + "LOC"
DEMO_LINE = DEMO_PREFIX + "LINE"
DEMO_MACHINE = DEMO_PREFIX + "VMC01"
DEMO_OPERATION = DEMO_PREFIX + "OP20"
DEMO_COMPONENT = DEMO_PREFIX + "PART0001"
DEMO_INSERT_TYPE = DEMO_PREFIX + "INSERT"
DEMO_INSERT_ITEM = DEMO_PREFIX + "INS0001N"
DEMO_HSN = "82075000"

# Production Line, Machine and CPC Component are named by expression, so the
# docname is the location code joined to the record code.
DEMO_LINE_ID = DEMO_LOCATION + "-" + DEMO_LINE
DEMO_MACHINE_ID = DEMO_LOCATION + "-" + DEMO_MACHINE
DEMO_COMPONENT_ID = DEMO_LOCATION + "-" + DEMO_COMPONENT


def run_p1_flow(company=None):
	"""Drive one tool through issue, installation, removal, return and disposition.

	Reproduces the BRS section 22 worked example: 100,000 at installation and
	104,600 at removal against a 5,000 planned life gives 92 percent achievement.
	"""
	company = company or frappe.db.get_value("Company", {}, "name")
	abbr = frappe.db.get_value("Company", company, "abbr")
	currency = frappe.db.get_value("Company", company, "default_currency")
	today = frappe.utils.nowdate()

	run_smoke_test(company=company)
	warehouses = _ensure_warehouses(company, abbr)
	customer = _ensure_customer()
	_ensure_location(company, warehouses, customer)
	_ensure_line_machine_operation()
	_ensure_component(customer)
	_ensure_insert_item(company)
	pfep = _ensure_pfep(today, customer)
	contract = _ensure_contract(company, currency, customer)

	out = {"pfep": pfep, "contract": contract}

	receipt = _submit(
		"TMS Tool Receipt",
		{
			"posting_date": today, "company": company, "customer": customer,
			"tms_location": DEMO_LOCATION, "receipt_type": "New Tool Supply",
			"items": [
				{"item_code": DEMO_TOOL + "N", "qty": 1, "rate": 15000},
				{"item_code": DEMO_INSERT_ITEM, "qty": 10, "rate": 500},
			],
		},
	)
	out["receipt"] = {"name": receipt.name, "stock_entry": receipt.stock_entry}

	issue = _submit(
		"TMS Tool Issue",
		{
			"posting_date": today, "company": company, "customer": customer,
			"tms_location": DEMO_LOCATION, "cpc_contract": contract,
			"cpc_component": DEMO_COMPONENT_ID, "machine": DEMO_MACHINE_ID,
			"operation": DEMO_OPERATION, "production_line": DEMO_LINE_ID,
			"items": [
				{"item_code": DEMO_TOOL + "N", "qty": 1, "is_primary_tool": 1},
				{"item_code": DEMO_INSERT_ITEM, "qty": 6},
			],
		},
	)
	issue.reload()
	out["issue"] = {
		"name": issue.name, "stock_entry": issue.stock_entry,
		"total_issue_value": issue.total_issue_value, "pfep": issue.pfep,
		"rows": [
			{"item": r.item_code, "qty": r.qty, "rate": r.valuation_rate,
			 "value": r.issue_value, "pfep_standard_qty": r.pfep_standard_qty,
			 "additional_qty": r.additional_qty, "planned_life": r.planned_tool_life}
			for r in issue.items
		],
	}

	installation = _submit(
		"TMS Tool Installation",
		{
			"posting_date": today, "company": company, "customer": customer,
			"tms_location": DEMO_LOCATION, "tool_issue": issue.name,
			"cpc_component": DEMO_COMPONENT_ID, "machine": DEMO_MACHINE_ID,
			"operation": DEMO_OPERATION, "item_code": DEMO_TOOL + "N",
			"installation_date": today, "starting_production_counter": 100000,
		},
	)
	out["installation"] = {
		"name": installation.name, "planned_life": installation.planned_tool_life,
		"status": installation.installation_status,
	}

	removal = _submit(
		"TMS Tool Removal",
		{
			"posting_date": today, "company": company,
			"tool_installation": installation.name, "removal_date": today,
			"ending_production_counter": 104600, "removal_reason": "Life Completed",
		},
	)
	out["removal"] = {
		"name": removal.name, "actual_tool_life": removal.actual_tool_life,
		"planned_tool_life": removal.planned_tool_life,
		"achievement_pct": removal.life_achievement_pct,
		"status": removal.tool_life_status,
	}

	tool_return = _submit(
		"TMS Tool Return",
		{
			"posting_date": today, "company": company, "customer": customer,
			"tms_location": DEMO_LOCATION, "tool_removal": removal.name,
			"cpc_component": DEMO_COMPONENT_ID, "return_date": today,
			"items": [
				{"item_code": DEMO_TOOL + "N", "qty": 1},
				{"item_code": DEMO_INSERT_ITEM, "qty": 6},
			],
		},
	)
	out["return"] = {"name": tool_return.name, "stock_entry": tool_return.stock_entry}

	inspection = _submit(
		"TMS Used Tool Inspection",
		{
			"posting_date": today, "company": company, "customer": customer,
			"tms_location": DEMO_LOCATION, "inspection_date": today,
			"items": [
				{"item_code": DEMO_TOOL + "N", "qty": 1, "inspection_result": "Worn",
				 "disposition": "Regrind", "cpc_component_last_used": DEMO_COMPONENT_ID},
				{"item_code": DEMO_INSERT_ITEM, "qty": 6, "inspection_result": "OK",
				 "disposition": "Reusable", "cpc_component_last_used": DEMO_COMPONENT_ID},
			],
		},
	)
	out["inspection"] = {
		"name": inspection.name, "summary": inspection.disposition_summary,
		"stock_entry": inspection.stock_entry,
	}

	out["closing_stock"] = _stock_snapshot(warehouses)
	frappe.db.commit()
	return out


def _submit(doctype, values):
	doc = frappe.new_doc(doctype)
	doc.update(values)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def _ensure_warehouses(company, abbr):
	names = {}
	for key, label in (("main_warehouse", "Main"), ("shopfloor_warehouse", "Shopfloor"),
	                   ("used_tool_warehouse", "Used Tool")):
		wh_name = "{0}{1} - {2}".format(DEMO_PREFIX, label, abbr)
		if not frappe.db.exists("Warehouse", wh_name):
			doc = frappe.new_doc("Warehouse")
			doc.warehouse_name = DEMO_PREFIX + label
			doc.company = company
			doc.insert(ignore_permissions=True)
			wh_name = doc.name
		names[key] = wh_name
	return names


def _ensure_customer():
	"""Customer naming may follow a series, so always resolve the real docname."""
	existing = frappe.db.get_value("Customer", {"customer_name": DEMO_CUSTOMER}, "name")
	if existing:
		return existing
	doc = frappe.new_doc("Customer")
	doc.customer_name = DEMO_CUSTOMER
	doc.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
	doc.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_location(company, warehouses, customer):
	if frappe.db.exists("TMS Customer Location", DEMO_LOCATION):
		return
	doc = frappe.new_doc("TMS Customer Location")
	doc.update({
		"tms_location_code": DEMO_LOCATION, "location_name": "Demo Engine Plant",
		"customer": customer, "plant": "Engine Plant", "company": company,
	})
	doc.update(warehouses)
	doc.insert(ignore_permissions=True)


def _ensure_line_machine_operation():
	if not frappe.db.exists("TMS Production Line", DEMO_LINE_ID):
		doc = frappe.new_doc("TMS Production Line")
		doc.update({"line_code": DEMO_LINE, "line_name": "Demo Engine Line",
		            "tms_location": DEMO_LOCATION})
		doc.insert(ignore_permissions=True)

	if not frappe.db.exists("TMS Customer Machine", DEMO_MACHINE_ID):
		doc = frappe.new_doc("TMS Customer Machine")
		doc.update({"machine_code": DEMO_MACHINE, "machine_name": "Demo VMC 01",
		            "tms_location": DEMO_LOCATION,
		            "production_line": DEMO_LINE_ID})
		doc.insert(ignore_permissions=True)

	if not frappe.db.exists("TMS Operation", DEMO_OPERATION):
		doc = frappe.new_doc("TMS Operation")
		doc.update({"operation_code": DEMO_OPERATION, "operation_name": "Demo Drilling OP20"})
		doc.insert(ignore_permissions=True)


def _ensure_component(customer):
	name = DEMO_COMPONENT_ID
	if frappe.db.exists("CPC Component", name):
		return
	doc = frappe.new_doc("CPC Component")
	doc.update({
		"component_code": DEMO_COMPONENT, "component_name": "Demo Cylinder Head",
		"customer": customer, "tms_location": DEMO_LOCATION,
		"production_line": DEMO_LINE_ID, "billing_uom": "Nos",
	})
	doc.append("operations", {
		"production_line": DEMO_LINE_ID,
		"machine": DEMO_MACHINE_ID,
		"operation": DEMO_OPERATION, "sequence": 20,
	})
	doc.insert(ignore_permissions=True)


def _ensure_insert_item(company):
	if not frappe.db.exists("TMS Tool Type", DEMO_INSERT_TYPE):
		doc = frappe.new_doc("TMS Tool Type")
		doc.update({
			"tool_type_code": DEMO_INSERT_TYPE, "tool_type_name": "Demo Carbide Insert",
			"tool_category": DEMO_CATEGORY, "is_regrindable": 0,
			"planned_new_tool_life": 800, "standard_new_tool_cost": 500, "default_uom": "Nos",
		})
		doc.insert(ignore_permissions=True)

	if frappe.db.exists("Item", DEMO_INSERT_ITEM):
		return
	# Inserts are shared quantity-based tooling, so they are not registered one
	# item code per physical piece (BRS section 32).
	item = frappe.new_doc("Item")
	item.update({
		"item_code": DEMO_INSERT_ITEM, "item_name": "Demo Carbide Insert - New",
		"item_group": "Consumable", "stock_uom": "Nos", "is_stock_item": 1,
		"include_item_in_manufacturing": 0,
		"tms_is_tool": 1, "tms_tool_type": DEMO_INSERT_TYPE, "tms_tool_condition": "N",
	})
	if item.meta.has_field("gst_hsn_code"):
		item.gst_hsn_code = DEMO_HSN
	item.insert(ignore_permissions=True)


def _ensure_pfep(today, customer):
	component = DEMO_COMPONENT_ID
	existing = frappe.db.exists(
		"PFEP Tooling Plan", {"cpc_component": component, "docstatus": 1}
	)
	if existing:
		return existing

	doc = frappe.new_doc("PFEP Tooling Plan")
	doc.update({
		"customer": customer, "tms_location": DEMO_LOCATION,
		"cpc_component": component, "production_line": DEMO_LINE_ID,
		"monthly_planned_volume": 25000, "effective_from": "2026-01-01",
	})
	doc.append("tools", {
		"machine": DEMO_MACHINE_ID, "operation": DEMO_OPERATION,
		"tool_type": DEMO_TOOL_TYPE, "is_primary_tool": 1,
		"tools_per_assembly": 1, "assemblies_per_machine": 1,
		"planned_new_tool_life": 5000, "planned_reground_tool_life": 4000,
	})
	doc.append("tools", {
		"machine": DEMO_MACHINE_ID, "operation": DEMO_OPERATION,
		"tool_type": DEMO_INSERT_TYPE, "tools_per_assembly": 6, "assemblies_per_machine": 1,
		"planned_new_tool_life": 800,
	})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def _ensure_contract(company, currency, customer):
	existing = frappe.db.exists(
		"CPC Contract", {"tms_location": DEMO_LOCATION, "docstatus": 1}
	)
	if existing:
		return existing

	doc = frappe.new_doc("CPC Contract")
	doc.update({
		"customer": customer, "tms_location": DEMO_LOCATION, "company": company,
		"customer_po_number": DEMO_PREFIX + "PO001", "currency": currency,
		"contract_start_date": "2026-01-01", "contract_end_date": "2026-12-31",
	})
	doc.append("components", {
		"cpc_component": DEMO_COMPONENT_ID,
		"machine": DEMO_MACHINE_ID, "operation": DEMO_OPERATION,
		"cpc_rate": 12, "effective_from": "2026-01-01", "effective_to": "2026-09-30",
		"po_quantity": 25000,
	})
	doc.append("components", {
		"cpc_component": DEMO_COMPONENT_ID,
		"machine": DEMO_MACHINE_ID, "operation": DEMO_OPERATION,
		"cpc_rate": 12.75, "effective_from": "2026-10-01", "effective_to": "2026-12-31",
	})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def _stock_snapshot(warehouses):
	snapshot = {}
	for key, warehouse in warehouses.items():
		rows = frappe.get_all(
			"Bin", filters={"warehouse": warehouse, "actual_qty": (">", 0)},
			fields=["item_code", "actual_qty"]
		)
		snapshot[key] = {r.item_code: r.actual_qty for r in rows}
	return snapshot


# --------------------------------------------------------------- P2 flow test

DEMO_BILLING_ITEM = DEMO_PREFIX + "CPC-CHARGES"


def run_p2_flow(company=None):
	"""Declare production, bill it, prove it cannot be billed twice, then invoice.

	Reproduces the BRS section 37 example: 25,000 accepted at a CPC rate of 12
	gives 300,000 billing value, compared against the tool issue value posted by
	the P1 flow.
	"""
	company = company or frappe.db.get_value("Company", {}, "name")
	currency = frappe.db.get_value("Company", company, "default_currency")
	today = frappe.utils.nowdate()
	month_start = frappe.utils.get_first_day(today)
	month_end = frappe.utils.get_last_day(today)

	customer = frappe.db.get_value("Customer", {"customer_name": DEMO_CUSTOMER}, "name")
	contract = frappe.db.get_value("CPC Contract", {"tms_location": DEMO_LOCATION,
	                                                "docstatus": 1}, "name")
	if not contract:
		frappe.throw("Run tms.setup.demo.run_p1_flow first.")

	_ensure_billing_item(company)
	out = {"contract": contract}

	declaration = _submit("TMS Production Declaration", {
		"posting_date": today, "company": company, "customer": customer,
		"tms_location": DEMO_LOCATION, "cpc_contract": contract,
		"production_line": DEMO_LINE_ID, "declaration_frequency": "Monthly",
		"from_date": month_start, "to_date": month_end,
		"confirmation_status": "Confirmed",
		"customer_confirmation_reference": DEMO_PREFIX + "CONF-001",
		"items": [{
			"production_date": today, "machine": DEMO_MACHINE_ID,
			"cpc_component": DEMO_COMPONENT_ID, "gross_production": 26000,
			"rejection_qty": 500, "rework_qty": 300, "non_billable_qty": 200,
		}],
	})
	declaration.reload()
	out["declaration"] = {
		"name": declaration.name,
		"gross": declaration.total_gross_production,
		"accepted": declaration.total_accepted_qty,
		"billable": declaration.total_billable_qty,
		"row_status": declaration.items[0].billing_status,
		"row_rate": declaration.items[0].cpc_rate,
	}

	statement = frappe.new_doc("TMS CPC Billing Statement")
	statement.update({
		"posting_date": today, "company": company, "customer": customer,
		"tms_location": DEMO_LOCATION, "cpc_contract": contract, "currency": currency,
		"billing_month": str(today)[:7], "from_date": month_start, "to_date": month_end,
	})
	fetched = statement.fetch_unbilled_production()
	statement.insert(ignore_permissions=True)
	statement.submit()
	statement.reload()

	out["billing"] = {
		"name": statement.name, "rows_fetched": fetched,
		"total_billing_qty": statement.total_billing_qty,
		"total_billing_value": statement.total_billing_value,
		"total_tool_issue_value": statement.total_tool_issue_value,
		"tool_issue_value_per_component": statement.tool_issue_value_per_component,
		"contribution_value": statement.contribution_value,
		"status": statement.billing_status,
	}

	declaration.reload()
	out["declaration_after_billing"] = {
		"billed_qty": declaration.items[0].billed_qty,
		"unbilled_qty": declaration.items[0].unbilled_qty,
		"billing_status": declaration.items[0].billing_status,
	}

	# duplicate control: a second statement for the same period finds nothing left
	probe = frappe.new_doc("TMS CPC Billing Statement")
	probe.update({
		"posting_date": today, "company": company, "customer": customer,
		"tms_location": DEMO_LOCATION, "cpc_contract": contract, "currency": currency,
		"from_date": month_start, "to_date": month_end,
	})
	out["rebill_attempt_rows"] = probe.fetch_unbilled_production()

	# and an explicit over-bill is refused
	over = frappe.new_doc("TMS CPC Billing Statement")
	over.update({
		"posting_date": today, "company": company, "customer": customer,
		"tms_location": DEMO_LOCATION, "cpc_contract": contract, "currency": currency,
		"from_date": month_start, "to_date": month_end,
		"items": [{
			"declaration_item": declaration.items[0].name,
			"production_declaration": declaration.name,
			"cpc_component": DEMO_COMPONENT_ID, "current_billing_qty": 100, "cpc_rate": 12,
		}],
	})
	try:
		over.insert(ignore_permissions=True)
		out["over_billing_blocked"] = False
	except frappe.ValidationError as exc:
		out["over_billing_blocked"] = True
		out["over_billing_message"] = str(exc).split("\n")[0][:120]

	out["sales_invoice"] = statement.make_sales_invoice()
	si = frappe.get_doc("Sales Invoice", out["sales_invoice"])
	out["sales_invoice_detail"] = {
		"grand_total": si.grand_total, "net_total": si.net_total,
		"cpc_contract": si.tms_cpc_contract, "billing_statement": si.tms_billing_statement,
		"items": [{"item": i.item_code, "qty": i.qty, "rate": i.rate,
		           "component": i.tms_cpc_component} for i in si.items],
	}

	frappe.db.commit()
	return out


def _ensure_billing_item(company):
	if not frappe.db.exists("Item", DEMO_BILLING_ITEM):
		item = frappe.new_doc("Item")
		item.update({
			"item_code": DEMO_BILLING_ITEM, "item_name": "Demo CPC Machining Charges",
			"item_group": "Services", "stock_uom": "Nos",
			"is_stock_item": 0, "is_sales_item": 1, "is_purchase_item": 0,
		})
		if item.meta.has_field("gst_hsn_code"):
			item.gst_hsn_code = DEMO_HSN
		item.insert(ignore_permissions=True)

	frappe.db.set_value("CPC Component", DEMO_COMPONENT_ID, "billing_item", DEMO_BILLING_ITEM)


# --------------------------------------------------------------- P3 flow test

def run_p3_flow(company=None):
	"""Two complete regrind cycles, proving the serial carries the regrind count.

	Cycle 1 takes the new drill through RGP to RGF-0001. The reground tool then
	goes back to site, is issued and returned, and cycle 2 produces RGF-0002
	chained to the first. Finally the tool is scrapped to show terminal blocking.
	"""
	company = company or frappe.db.get_value("Company", {}, "name")
	abbr = frappe.db.get_value("Company", company, "abbr")
	today = frappe.utils.nowdate()
	customer = frappe.db.get_value("Customer", {"customer_name": DEMO_CUSTOMER}, "name")
	contract = frappe.db.get_value("CPC Contract", {"tms_location": DEMO_LOCATION,
	                                                "docstatus": 1}, "name")
	ho = _ensure_head_office(company, abbr)
	out = {"head_office_warehouse": ho}

	base = {"posting_date": today, "company": company, "customer": customer,
	        "tms_location": DEMO_LOCATION}

	# ---- cycle 1: the new tool goes for its first regrind
	cycle1 = _run_one_cycle(base, ho, DEMO_TOOL + "N", None, today)
	out["cycle_1"] = cycle1

	# ---- reground tool returns to the customer location
	receipt = _submit("TMS Tool Receipt", dict(base, **{
		"receipt_type": "Reground Tool Return", "source_warehouse": ho,
		"items": [{"item_code": DEMO_TOOL + "RGF", "qty": 1,
		           "serial_no": cycle1["output_serial_no"]}],
	}))
	out["reground_receipt"] = {"name": receipt.name, "stock_entry": receipt.stock_entry}

	# ---- issued again, this time a serialised reground tool
	issue = _submit("TMS Tool Issue", dict(base, **{
		"cpc_contract": contract, "cpc_component": DEMO_COMPONENT_ID,
		"machine": DEMO_MACHINE_ID, "operation": DEMO_OPERATION,
		"production_line": DEMO_LINE_ID,
		"items": [{"item_code": DEMO_TOOL + "RGF", "qty": 1,
		           "serial_no": cycle1["output_serial_no"], "is_primary_tool": 1}],
	}))
	issue.reload()
	out["reground_issue"] = {
		"name": issue.name, "total_issue_value": issue.total_issue_value,
		"planned_life": issue.items[0].planned_tool_life,
		"regrind_cycle_on_issue": issue.items[0].regrind_cycle,
		"valuation_rate": issue.items[0].valuation_rate,
	}

	# ---- back to used stock and dispositioned for a second regrind
	_submit("TMS Tool Return", dict(base, **{
		"cpc_component": DEMO_COMPONENT_ID, "return_date": today,
		"items": [{"item_code": DEMO_TOOL + "RGF", "qty": 1,
		           "serial_no": cycle1["output_serial_no"]}],
	}))
	_submit("TMS Used Tool Inspection", dict(base, **{
		"inspection_date": today,
		"items": [{"item_code": DEMO_TOOL + "RGF", "qty": 1,
		           "serial_no": cycle1["output_serial_no"],
		           "inspection_result": "Worn", "disposition": "Regrind",
		           "cpc_component_last_used": DEMO_COMPONENT_ID}],
	}))

	# ---- cycle 2
	cycle2 = _run_one_cycle(base, ho, DEMO_TOOL + "RGF", cycle1["output_serial_no"], today)
	out["cycle_2"] = cycle2

	# ---- serial chain and regrind position
	from tms.tms.doctype.tms_regrind_cycle.tms_regrind_cycle import get_regrind_status
	out["serials"] = [
		frappe.db.get_value("Serial No", s, ["name", "item_code", "tms_regrind_cycle",
		                                     "tms_previous_serial_no", "tms_physical_tool_code"],
		                    as_dict=True)
		for s in (cycle1["output_serial_no"], cycle2["output_serial_no"])
	]
	status = get_regrind_status(DEMO_TOOL)
	out["regrind_status"] = {k: status[k] for k in
	                         ("completed_regrind_count", "max_regrind_count", "remaining_regrinds")}

	# ---- scrap the tool and prove the terminal condition blocks reissue
	scrap = _submit("TMS Tool Scrap", dict(base, **{
		"scrap_warehouse": ho, "scrap_date": today, "approved_by": "Administrator",
		"items": [{"item_code": DEMO_TOOL + "RGF", "qty": 1,
		           "serial_no": cycle2["output_serial_no"],
		           "scrap_reason": "Life Exhausted", "scrap_value": 250,
		           "cpc_component_last_used": DEMO_COMPONENT_ID}],
	}))
	out["scrap"] = {"name": scrap.name, "total_scrap_value": scrap.total_scrap_value}

	from tms.utils import validation as tms_validate
	try:
		tms_validate.validate_issuable(DEMO_TOOL + "SCR")
		out["scrap_blocked_from_issue"] = False
	except frappe.ValidationError as exc:
		out["scrap_blocked_from_issue"] = True
		out["scrap_block_message"] = str(exc).split("\n")[0][:120]

	out["closing_stock"] = _regrind_stock_snapshot(ho)
	frappe.db.commit()
	return out


def _run_one_cycle(base, ho, source_item, source_serial, today):
	"""Regrinding return, RGP conversion, then completion into a new RGF serial."""
	ret = _submit("TMS Regrinding Return", dict(base, **{
		"target_warehouse": ho, "dispatch_date": today,
		"gate_pass_reference": DEMO_PREFIX + "GP",
		"items": [{"item_code": source_item, "qty": 1, "serial_no": source_serial,
		           "cpc_component_last_used": DEMO_COMPONENT_ID,
		           "machine": DEMO_MACHINE_ID, "operation": DEMO_OPERATION,
		           "return_reason": "Regrind"}],
	}))
	ret.reload()

	cycle = frappe.get_doc("TMS Regrind Cycle", ret.items[0].regrind_cycle)
	cycle.regrind_cost = 2500
	cycle.save(ignore_permissions=True)
	cycle.submit()
	cycle.reload()

	rgp_status = cycle.status
	serial = cycle.complete_regrind(inspection_result="Accepted")
	cycle.reload()

	rgf_rate = frappe.db.get_value(
		"Stock Entry Detail",
		{"parent": cycle.rgf_stock_entry, "item_code": cycle.rgf_item}, "basic_rate"
	)

	return {
		"regrinding_return": ret.name,
		"cycle": cycle.name,
		"status_after_rgp": rgp_status,
		"cycle_number": cycle.cycle_number,
		"rgp_stock_entry": cycle.rgp_stock_entry,
		"rgf_stock_entry": cycle.rgf_stock_entry,
		"output_serial_no": serial,
		"completed_regrind_count": cycle.completed_regrind_count,
		"remaining_regrinds": cycle.remaining_regrinds,
		"reground_valuation": rgf_rate,
		"status": cycle.status,
	}


def _ensure_head_office(company, abbr):
	name = "{0}HeadOffice - {1}".format(DEMO_PREFIX, abbr)
	if not frappe.db.exists("Warehouse", name):
		doc = frappe.new_doc("Warehouse")
		doc.warehouse_name = DEMO_PREFIX + "HeadOffice"
		doc.company = company
		doc.insert(ignore_permissions=True)
		name = doc.name
	frappe.db.set_value("TMS Customer Location", DEMO_LOCATION, "head_office_warehouse", name)
	return name


def _regrind_stock_snapshot(ho):
	rows = frappe.get_all(
		"Bin",
		filters={"item_code": ("like", DEMO_TOOL + "%"), "actual_qty": (">", 0)},
		fields=["item_code", "warehouse", "actual_qty"],
	)
	return [{"item": r.item_code, "warehouse": r.warehouse, "qty": r.actual_qty} for r in rows]


# ------------------------------------------------- regrind valuation check

DEMO_TOOL_2 = DEMO_PREFIX + "T0002"


def check_regrind_valuation(company=None):
	"""Assert that value survives both condition conversions.

	A new tool received at 15,000 and reground for 2,500 must come out of the
	cycle valued at 17,500. This guards the ERPNext behaviour where a Repack
	zeroes the finished-good rate if allow_zero_valuation_rate is left on.
	"""
	company = company or frappe.db.get_value("Company", {}, "name")
	abbr = frappe.db.get_value("Company", company, "abbr")
	today = frappe.utils.nowdate()
	customer = frappe.db.get_value("Customer", {"customer_name": DEMO_CUSTOMER}, "name")
	ho = _ensure_head_office(company, abbr)

	_ensure_category()
	_ensure_tool_type()

	if not frappe.db.exists("TMS Tool Registration", {"physical_tool_code": DEMO_TOOL_2,
	                                                  "docstatus": 1}):
		reg = frappe.new_doc("TMS Tool Registration")
		reg.update({
			"physical_tool_code": DEMO_TOOL_2, "tool_type": DEMO_TOOL_TYPE,
			"tool_description": "Demo Carbide Drill 12mm (valuation check)",
			"company": company, "item_group": "Consumable", "stock_uom": "Nos",
			"gst_hsn_code": DEMO_HSN,
		})
		reg.fetch_conditions()
		reg.insert(ignore_permissions=True)
		reg.submit()

	base = {"posting_date": today, "company": company, "customer": customer,
	        "tms_location": DEMO_LOCATION}

	receipt = _submit("TMS Tool Receipt", dict(base, **{
		"receipt_type": "New Tool Supply", "target_warehouse": ho,
		"items": [{"item_code": DEMO_TOOL_2 + "N", "qty": 1, "rate": 15000}],
	}))
	# receipt lands in the main warehouse by design, so move it to Head Office
	frappe.db.set_value("TMS Customer Location", DEMO_LOCATION, "head_office_warehouse", ho)

	cycle = frappe.new_doc("TMS Regrind Cycle")
	cycle.update({
		"posting_date": today, "company": company, "customer": customer,
		"tms_location": DEMO_LOCATION, "physical_tool_code": DEMO_TOOL_2,
		"tool_type": DEMO_TOOL_TYPE, "source_item": DEMO_TOOL_2 + "N",
		"qty": 1, "ho_warehouse": receipt.target_warehouse, "regrind_cost": 2500,
	})
	cycle.insert(ignore_permissions=True)
	cycle.submit()
	serial = cycle.complete_regrind(inspection_result="Accepted")
	cycle.reload()

	def rate_for(entry, item):
		# valuation_rate is the true landed value: basic_rate plus additional cost
		return frappe.db.get_value(
			"Stock Entry Detail", {"parent": entry, "item_code": item}, "valuation_rate"
		)

	result = {
		"receipt": receipt.name,
		"warehouse": receipt.target_warehouse,
		"new_tool_rate": rate_for(receipt.stock_entry, DEMO_TOOL_2 + "N"),
		"rgp_rate": rate_for(cycle.rgp_stock_entry, DEMO_TOOL_2 + "RGP"),
		"rgf_rate": rate_for(cycle.rgf_stock_entry, DEMO_TOOL_2 + "RGF"),
		"regrind_cost": cycle.regrind_cost,
		"output_serial_no": serial,
		"cycle_number": cycle.cycle_number,
	}
	result["expected_rgf_rate"] = flt(result["rgp_rate"]) + flt(cycle.regrind_cost)
	result["valuation_correct"] = (
		abs(flt(result["rgf_rate"]) - flt(result["expected_rgf_rate"])) < 0.01
	)
	frappe.db.commit()
	return result
