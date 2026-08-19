# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt
"""Shared TMS business validations (BRS section 48)."""

import frappe
from frappe import _
from frappe.utils import flt, getdate


def get_item_tool_info(item_code):
	"""Tool metadata carried on the Item by TMS Tool Registration."""
	info = frappe.db.get_value(
		"Item",
		item_code,
		["tms_is_tool", "tms_tool_type", "tms_tool_condition", "tms_physical_tool_code",
		 "has_serial_no", "stock_uom"],
		as_dict=True,
	)
	return info or frappe._dict()


def get_condition_flags(condition_code):
	if not condition_code:
		return frappe._dict()
	return frappe.db.get_value(
		"TMS Tool Condition",
		condition_code,
		["is_usable", "is_regrind_input", "is_regrind_output", "is_terminal", "serialised"],
		as_dict=True,
	) or frappe._dict()


def validate_issuable(item_code):
	"""Rules 11, 12 and 15: scrap, rejected and regrinding-pending tools cannot be issued."""
	info = get_item_tool_info(item_code)
	if not info.get("tms_is_tool"):
		return info

	flags = get_condition_flags(info.tms_tool_condition)
	condition_name = frappe.db.get_value(
		"TMS Tool Condition", info.tms_tool_condition, "condition_name"
	) or info.tms_tool_condition

	if flags.get("is_terminal"):
		frappe.throw(
			_("{0} is in condition {1} and is permanently blocked from issue.").format(
				item_code, condition_name
			),
			title=_("Tool Blocked"),
		)

	if not flags.get("is_usable"):
		frappe.throw(
			_("{0} is in condition {1} and cannot be issued for production.").format(
				item_code, condition_name
			),
			title=_("Tool Not Usable"),
		)

	return info


def validate_machine_operation(cpc_component, machine, operation):
	"""Rule 6: machine and operation must be defined on the component."""
	if not (cpc_component and machine and operation):
		return

	exists = frappe.db.exists(
		"CPC Component Operation",
		{"parent": cpc_component, "machine": machine, "operation": operation},
	)
	if not exists:
		frappe.throw(
			_("Machine {0} with Operation {1} is not defined on CPC Component {2}.").format(
				machine, operation, cpc_component
			),
			title=_("Invalid Machine or Operation"),
		)


def validate_active_contract(cpc_contract, cpc_component, posting_date):
	"""Rule 19 and section 12: the contract must be live and cover the component."""
	if not cpc_contract:
		return

	contract = frappe.db.get_value(
		"CPC Contract",
		cpc_contract,
		["docstatus", "status", "contract_start_date", "contract_end_date", "tms_location"],
		as_dict=True,
	)
	if not contract:
		frappe.throw(_("CPC Contract {0} does not exist.").format(cpc_contract))

	if contract.docstatus != 1:
		frappe.throw(_("CPC Contract {0} is not submitted.").format(cpc_contract))

	if not (getdate(contract.contract_start_date) <= getdate(posting_date)
	        <= getdate(contract.contract_end_date)):
		frappe.throw(
			_("Posting date {0} falls outside the period of CPC Contract {1} ({2} to {3}).").format(
				posting_date, cpc_contract, contract.contract_start_date, contract.contract_end_date
			),
			title=_("Contract Not Active"),
		)

	if cpc_component and not frappe.db.exists(
		"CPC Contract Component", {"parent": cpc_contract, "cpc_component": cpc_component}
	):
		frappe.throw(
			_("CPC Component {0} is not covered by CPC Contract {1}.").format(
				cpc_component, cpc_contract
			),
			title=_("Component Not In Contract"),
		)


def get_pfep_plan(cpc_component, posting_date):
	from tms.tms.doctype.pfep_tooling_plan.pfep_tooling_plan import get_active_pfep

	pfep = get_active_pfep(cpc_component, posting_date)
	return frappe.get_cached_doc("PFEP Tooling Plan", pfep) if pfep else None


def get_pfep_standard_qty(pfep, tool_type, machine, operation):
	"""Standard quantity planned for a tool at a machine/operation (section 39)."""
	if not pfep:
		return 0, None

	for row in pfep.tools:
		if row.tool_type != tool_type:
			continue
		if machine and row.machine != machine:
			continue
		if operation and row.operation != operation:
			continue
		qty = flt(row.tools_per_assembly) * flt(row.assemblies_per_machine or 1)
		return qty, row

	return 0, None


def get_serial_regrind_cycle(serial_no):
	if not serial_no:
		return 0
	return int(frappe.db.get_value("Serial No", serial_no, "tms_regrind_cycle") or 0)


def validate_regrind_capacity(item_code, serial_no=None):
	"""Rules 17 and 18: a tool at its maximum regrind count cannot start another cycle."""
	info = get_item_tool_info(item_code)
	if not info.get("tms_tool_type"):
		return

	tool_type = frappe.db.get_value(
		"TMS Tool Type", info.tms_tool_type, ["is_regrindable", "max_regrind_count"], as_dict=True
	)
	if not tool_type or not tool_type.is_regrindable:
		frappe.throw(
			_("Tool Type {0} is not regrindable.").format(info.tms_tool_type),
			title=_("Not Regrindable"),
		)

	completed = get_serial_regrind_cycle(serial_no)
	if completed >= flt(tool_type.max_regrind_count):
		frappe.throw(
			_("{0} has completed {1} of {2} permitted regrinds. "
			  "An engineering exception is required to regrind it again.").format(
				serial_no or item_code, completed, tool_type.max_regrind_count
			),
			title=_("Maximum Regrind Count Reached"),
		)


def get_settings():
	return frappe.get_cached_doc("TMS Settings")


def get_tool_life_status(achievement_pct):
	"""Section 23 achievement bands, thresholds configurable in TMS Settings."""
	settings = get_settings()
	achieved = flt(settings.achieved_threshold) or 100
	near = flt(settings.near_target_threshold) or 90

	if flt(achievement_pct) >= achieved:
		return "Achieved"
	if flt(achievement_pct) >= near:
		return "Near Target"
	return "Below Target"
