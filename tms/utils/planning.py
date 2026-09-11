# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt
"""Replenishment planning (BRS sections 41 and 42).

Requirement is planned at Tool Type level, not per item code. Under the design
rule of one physical tool to one item code, per-item minimum and maximum stock
would always be zero or one, so "do I have enough usable tools of this type" is
the only question that means anything.
"""

import math

import frappe
from frappe.utils import flt

from tms.tms.doctype.pfep_tooling_plan.pfep_tooling_plan import get_active_pfep


def build_requirement_rows(source_warehouse,target_warehouse,cpc_component=None, posting_date=None,
                           monthly_volume_override=None, working_days=26):
	posting_date = posting_date or frappe.utils.nowdate()
	#location = frappe.get_cached_doc("TMS Customer Location", tms_location)

	components = [cpc_component] if cpc_component else frappe.get_all(
		"CPC Component",
		filters={"is_active": 1},
		pluck="name",
	)

	rows = []
	for component in components:
		pfep_name = get_active_pfep(component, posting_date)
		if not pfep_name:
			continue

		pfep = frappe.get_cached_doc("PFEP Tooling Plan", pfep_name)
		monthly_volume = flt(monthly_volume_override) or flt(pfep.monthly_planned_volume)

		for tool in pfep.tools:
			rows.append(_plan_one_tool(source_warehouse,target_warehouse, pfep, tool, component, monthly_volume,
			                           working_days))

	return rows


def _plan_one_tool(source_warehouse,target_warehouse,pfep, tool, component, monthly_volume, working_days):
	tool_registration = tool.tms_tool_registration
	planned_life = flt(tool.planned_new_tool_life)
	per_assembly = flt(tool.tools_per_assembly) or 1
	assemblies = flt(tool.assemblies_per_machine) or 1

	gross = 0.0
	if planned_life > 0 and monthly_volume > 0:
		gross = (monthly_volume / planned_life) * per_assembly * assemblies

	available = get_usable_stock(tool_registration,source_warehouse)
	expected_regrind = get_expected_regrind_qty(tool_registration)
	open_transfer = get_open_material_request_qty(tool_registration)
	open_purchase = get_open_purchase_qty(tool_registration)
	open_manufacturing = get_open_manufacturing_qty(tool_registration)

	net = (
		gross + flt(tool.safety_stock)
		- available - expected_regrind - open_transfer - open_purchase - open_manufacturing
	)
	# tools are discrete, so a shortage of 177.5 means 178 tools have to be found
	net = math.ceil(max(net, 0))

	daily_production = (monthly_volume / working_days) if working_days else 0
	components_producible = 0.0
	if per_assembly and assemblies:
		components_producible = (available / (per_assembly * assemblies)) * planned_life
	safe_days = (components_producible / daily_production) if daily_production else 0

	return {
		"tool_type": tool.tool_type,
		"tms_tool_registration": tool_registration,
		"item_code": resolve_preferred_item(tool_registration),
		"cpc_component": component,
		"machine": tool.machine,
		"operation": tool.operation,
		"planned_tool_life": planned_life,
		"tools_per_assembly": per_assembly,
		"assemblies_per_machine": assemblies,
		"gross_requirement": gross,
		"safety_stock": flt(tool.safety_stock),
		"available_qty": available,
		"expected_regrind_qty": expected_regrind,
		"open_transfer_qty": open_transfer,
		"open_purchase_qty": open_purchase,
		"open_manufacturing_qty": open_manufacturing,
		"net_requirement": net,
		"min_stock": flt(tool.min_stock),
		"max_stock": flt(tool.max_stock),
		"stock_status": get_stock_status(available, tool),
		"safe_running_days": safe_days,
		"recommended_action": recommend_action(net, tool, target_warehouse, expected_regrind),
		"requested_qty": net,
	}


def get_usable_stock(tool_registration, warehouse):
	"""Stock of a tool type in any condition that may be issued for production."""
	if not (tool_registration and warehouse):
		return 0.0
	return flt(frappe.db.sql(
		"""
		select coalesce(sum(b.actual_qty), 0)
		from tabBin b
		inner join tabItem i on i.name = b.item_code
		inner join `tabTMS Tool Condition` c on c.name = i.tms_tool_condition
		where b.warehouse = %(warehouse)s and i.custom_tms_tool_registration = %(tool_registration)s
		  and c.is_usable = 1
		""",
		{"warehouse": warehouse, "tool_registration": tool_registration},
	)[0][0])


def get_expected_regrind_qty(tool_registration):
	"""Tools already in a regrind cycle that will come back as usable stock."""
	return flt(frappe.db.sql(
		"""
		select coalesce(sum(qty), 0) from `tabTMS Regrind Cycle`
		where docstatus = 1 and status = 'Pending Regrinding' and tool_registration = %(tool_registration)s
		""",
		{"tool_registration": tool_registration},
	)[0][0])


def get_open_material_request_qty(tool_registration):
	return flt(frappe.db.sql(
		"""
		select coalesce(sum(mri.qty - ifnull(mri.received_qty, 0)), 0)
		from `tabMaterial Request Item` mri
		inner join `tabMaterial Request` mr on mr.name = mri.parent
		inner join tabItem i on i.name = mri.item_code
		where mr.docstatus = 1 and mr.status not in ('Stopped', 'Cancelled')
		  and i.custom_tms_tool_registration = %(tool_registration)s
		  and (mri.qty - ifnull(mri.received_qty, 0)) > 0
		""",
		{"tool_registration": tool_registration},
	)[0][0])


def get_open_purchase_qty(tool_registration):
	return flt(frappe.db.sql(
		"""
		select coalesce(sum(poi.qty - ifnull(poi.received_qty, 0)), 0)
		from `tabPurchase Order Item` poi
		inner join `tabPurchase Order` po on po.name = poi.parent
		inner join tabItem i on i.name = poi.item_code
		where po.docstatus = 1 and po.status not in ('Closed', 'Completed')
		  and i.custom_tms_tool_registration = %(tool_registration)s
		  and (poi.qty - ifnull(poi.received_qty, 0)) > 0
		""",
		{"tool_registration": tool_registration},
	)[0][0])


def get_open_manufacturing_qty(tool_registration):
	return flt(frappe.db.sql(
		"""
		select coalesce(sum(wo.qty - ifnull(wo.produced_qty, 0)), 0)
		from `tabWork Order` wo
		inner join tabItem i on i.name = wo.production_item
		where wo.docstatus = 1 and wo.status not in ('Completed', 'Stopped', 'Closed')
		  and i.custom_tms_tool_registration = %(tool_registration)s
		""",
		{"tool_registration": tool_registration},
	)[0][0])


def resolve_preferred_item(tool_registration):
	"""Return an item code only when the type maps to a single shared item.

	Consumables such as inserts have one item code for many physical pieces, so a
	requirement can name the item directly. Regrindable main tools have one item
	code per physical tool, so there is nothing sensible to name until the planner
	registers or picks a specific tool.
	"""
	items = frappe.db.sql(
		"""
		select i.name
		from tabItem i
		inner join `tabTMS Tool Condition` c on c.name = i.tms_tool_condition
		where i.custom_tms_tool_registration = %(tool_registration)s and c.name = 'N' and i.disabled = 0
		""",
		{"tool_registration": tool_registration},
		pluck=True,
	)
	return items[0] if len(items) == 1 else None


def get_stock_status(available, tool):
	if available <= 0:
		return "Critical"
	if flt(tool.min_stock) and available < flt(tool.min_stock):
		return "Reorder Required"
	if flt(tool.max_stock) and available > flt(tool.max_stock):
		return "Excess"
	return "Adequate"


def recommend_action(net, tool, target_warehouse, expected_regrind):
	"""Prefer stock the business already owns before buying more."""
	if net <= 0:
		return "No Requirement"

	#head_office = location.head_office_warehouse
	if target_warehouse:
		reground = get_condition_stock(tool.tool_type, target_warehouse, "is_regrind_output")
		if reground > 0:
			return "Transfer Reground Tool"

		new_stock = get_condition_stock(tool.tool_type, target_warehouse, "is_usable")
		if new_stock > 0:
			return "Transfer New Tool"

	if expected_regrind > 0:
		return "Expedite Regrinding"

	return "Purchase"


def get_condition_stock(tool_registration, warehouse, condition_flag):
	if condition_flag not in ("is_usable", "is_regrind_output"):
		frappe.throw("Unsupported condition flag")

	return flt(frappe.db.sql(
		"""
		select coalesce(sum(b.actual_qty), 0)
		from tabBin b
		inner join tabItem i on i.name = b.item_code
		inner join `tabTMS Tool Condition` c on c.name = i.tms_tool_condition
		where b.warehouse = %(warehouse)s and i.custom_tms_tool_registration = %(tool_registration)s
		  and c.{flag} = 1
		""".format(flag=condition_flag),
		{"warehouse": warehouse, "tool_registration": tool_registration},
	)[0][0])
