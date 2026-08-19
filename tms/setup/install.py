# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

TMS_ROLES = [
	"TMS Site User",
	"TMS Site Supervisor",
	"TMS Head Office User",
	"TMS Engineering User",
	"TMS Commercial User",
	"TMS Manager",
]

# Condition master seeded from BRS section 7. The suffix builds the condition item
# code for a physical tool, e.g. T0001 + RGF -> T0001RGF.
TOOL_CONDITIONS = [
	{
		"condition_code": "N",
		"condition_name": "New",
		"item_code_suffix": "N",
		"is_usable": 1,
		"is_regrind_input": 1,
		"sort_order": 1,
		"description": "New tool available for production issue.",
	},
	{
		"condition_code": "RGP",
		"condition_name": "Regrinding Pending",
		"item_code_suffix": "RGP",
		"sort_order": 2,
		"description": "Tool accepted into regrinding. Blocked from production issue.",
	},
	{
		"condition_code": "RGF",
		"condition_name": "Regrinding Finished",
		"item_code_suffix": "RGF",
		"is_usable": 1,
		"is_regrind_input": 1,
		"is_regrind_output": 1,
		"serialised": 1,
		"sort_order": 3,
		"description": "Reground tool ready for reuse. Serialised; the serial carries the regrind cycle.",
	},
	{
		"condition_code": "REJ",
		"condition_name": "Rejected",
		"item_code_suffix": "REJ",
		"is_terminal": 1,
		"sort_order": 4,
		"description": "Rejected at inspection. Permanently blocked from issue and regrinding.",
	},
	{
		"condition_code": "SCR",
		"condition_name": "Scrap",
		"item_code_suffix": "SCR",
		"is_terminal": 1,
		"sort_order": 5,
		"description": "Scrapped tool. Permanently blocked from issue and regrinding.",
	},
]

CUSTOM_FIELDS = {
	"Item": [
		{
			"fieldname": "tms_section",
			"label": "Tool Management",
			"fieldtype": "Section Break",
			"insert_after": "item_group",
			"collapsible": 1,
		},
		{
			"fieldname": "tms_is_tool",
			"label": "Is TMS Tool",
			"fieldtype": "Check",
			"insert_after": "tms_section",
			"description": "Set automatically by TMS Tool Registration.",
		},
		{
			"fieldname": "tms_tool_type",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "TMS Tool Type",
			"insert_after": "tms_is_tool",
			"depends_on": "eval:doc.tms_is_tool",
		},
		{
			"fieldname": "tms_tool_condition",
			"label": "Tool Condition",
			"fieldtype": "Link",
			"options": "TMS Tool Condition",
			"insert_after": "tms_tool_type",
			"depends_on": "eval:doc.tms_is_tool",
		},
		{
			"fieldname": "tms_column",
			"fieldtype": "Column Break",
			"insert_after": "tms_tool_condition",
		},
		{
			"fieldname": "tms_physical_tool_code",
			"label": "Physical Tool Code",
			"fieldtype": "Data",
			"insert_after": "tms_column",
			"depends_on": "eval:doc.tms_is_tool",
			"description": "Base code shared by every condition item of one physical tool.",
		},
		{
			"fieldname": "tms_max_regrind_count",
			"label": "Maximum Regrind Count",
			"fieldtype": "Int",
			"insert_after": "tms_physical_tool_code",
			"fetch_from": "tms_tool_type.max_regrind_count",
			"read_only": 1,
			"depends_on": "eval:doc.tms_is_tool",
		},
	],
	"Serial No": [
		{
			"fieldname": "tms_section",
			"label": "Tool Management",
			"fieldtype": "Section Break",
			"insert_after": "warehouse",
			"collapsible": 1,
		},
		{
			"fieldname": "tms_tool_type",
			"label": "Tool Type",
			"fieldtype": "Link",
			"options": "TMS Tool Type",
			"insert_after": "tms_section",
			"read_only": 1,
		},
		{
			"fieldname": "tms_physical_tool_code",
			"label": "Physical Tool Code",
			"fieldtype": "Data",
			"insert_after": "tms_tool_type",
			"read_only": 1,
		},
		{
			"fieldname": "tms_regrind_cycle",
			"label": "Regrind Cycle",
			"fieldtype": "Int",
			"insert_after": "tms_physical_tool_code",
			"read_only": 1,
			"description": "Completed regrind count carried by this serial. Stamped when the reground tool is received.",
		},
		{
			"fieldname": "tms_column",
			"fieldtype": "Column Break",
			"insert_after": "tms_regrind_cycle",
		},
		{
			"fieldname": "tms_previous_serial_no",
			"label": "Previous Serial No",
			"fieldtype": "Data",
			"insert_after": "tms_column",
			"read_only": 1,
			"description": "Serial consumed to produce this one, giving the tool's cycle chain.",
		},
		{
			"fieldname": "tms_last_cpc_component",
			"label": "Last CPC Component",
			"fieldtype": "Link",
			"options": "CPC Component",
			"insert_after": "tms_previous_serial_no",
			"read_only": 1,
		},
	],
	"Stock Entry": [
		{
			"fieldname": "tms_section",
			"label": "Tool Management",
			"fieldtype": "Section Break",
			"insert_after": "company",
			"collapsible": 1,
		},
		{
			"fieldname": "tms_reference_doctype",
			"label": "TMS Reference Type",
			"fieldtype": "Link",
			"options": "DocType",
			"insert_after": "tms_section",
			"read_only": 1,
		},
		{
			"fieldname": "tms_reference_name",
			"label": "TMS Reference",
			"fieldtype": "Dynamic Link",
			"options": "tms_reference_doctype",
			"insert_after": "tms_reference_doctype",
			"read_only": 1,
		},
		{
			"fieldname": "tms_column",
			"fieldtype": "Column Break",
			"insert_after": "tms_reference_name",
		},
		{
			"fieldname": "tms_location",
			"label": "TMS Customer Location",
			"fieldtype": "Link",
			"options": "TMS Customer Location",
			"insert_after": "tms_column",
			"read_only": 1,
		},
		{
			"fieldname": "tms_cpc_component",
			"label": "CPC Component",
			"fieldtype": "Link",
			"options": "CPC Component",
			"insert_after": "tms_location",
			"read_only": 1,
		},
	],
	"Sales Invoice": [
		{
			"fieldname": "tms_section",
			"label": "Tool Management",
			"fieldtype": "Section Break",
			"insert_after": "po_no",
			"collapsible": 1,
		},
		{
			"fieldname": "tms_cpc_contract",
			"label": "CPC Contract",
			"fieldtype": "Link",
			"options": "CPC Contract",
			"insert_after": "tms_section",
			"read_only": 1,
		},
		{
			"fieldname": "tms_billing_statement",
			"label": "CPC Billing Statement",
			"fieldtype": "Link",
			"options": "TMS CPC Billing Statement",
			"insert_after": "tms_cpc_contract",
			"read_only": 1,
		},
		{
			"fieldname": "tms_column",
			"fieldtype": "Column Break",
			"insert_after": "tms_billing_statement",
		},
		{
			"fieldname": "tms_location",
			"label": "TMS Customer Location",
			"fieldtype": "Link",
			"options": "TMS Customer Location",
			"insert_after": "tms_column",
			"read_only": 1,
		},
		{
			"fieldname": "tms_billing_period",
			"label": "Billing Period",
			"fieldtype": "Data",
			"insert_after": "tms_location",
			"read_only": 1,
		},
	],
	"Sales Invoice Item": [
		{
			"fieldname": "tms_cpc_component",
			"label": "CPC Component",
			"fieldtype": "Link",
			"options": "CPC Component",
			"insert_after": "item_name",
			"read_only": 1,
		},
	],
}


def after_install():
	setup_tms()


def after_migrate():
	setup_tms()


def setup_tms():
	create_roles()
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	seed_tool_conditions()
	frappe.db.commit()


def create_roles():
	for role_name in TMS_ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		role = frappe.new_doc("Role")
		role.role_name = role_name
		role.desk_access = 1
		role.insert(ignore_permissions=True)


def seed_tool_conditions():
	for condition in TOOL_CONDITIONS:
		if frappe.db.exists("TMS Tool Condition", condition["condition_code"]):
			continue
		doc = frappe.new_doc("TMS Tool Condition")
		doc.update(condition)
		doc.insert(ignore_permissions=True)


def import_tool_categories_from_unitec_app():
	"""Optional one-off: seed TMS Tool Category from the existing Tool Type list.

	spokes_unitec_app carries a curated list of tool categories. TMS keeps its own
	master so it stays installable on sites without that app, but where the app is
	present the existing values are worth reusing rather than retyping.
	"""
	if not frappe.db.exists("DocType", "Tool Type"):
		frappe.throw("Tool Type doctype not found. This helper needs spokes_unitec_app installed.")

	created = 0
	for row in frappe.get_all("Tool Type", pluck="name"):
		name = (row or "").strip()
		if not name or frappe.db.exists("TMS Tool Category", name):
			continue
		doc = frappe.new_doc("TMS Tool Category")
		doc.category_name = name
		doc.insert(ignore_permissions=True)
		created += 1

	frappe.db.commit()
	return created
