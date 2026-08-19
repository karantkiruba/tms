# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TMSToolRegistration(Document):
	"""Registers one physical tool and generates its condition-wise Item codes.

	The design rule is one physical tool = one item code per condition, so a tool
	registered as T0001 yields T0001N, T0001RGP, T0001RGF and so on. The serial
	number series on the reground item carries that tool's regrind cycle.
	"""

	def validate(self):
		self.validate_duplicate()
		self.set_item_codes()

	def validate_duplicate(self):
		existing = frappe.db.exists(
			"TMS Tool Registration",
			{
				"physical_tool_code": self.physical_tool_code,
				"docstatus": ("<", 2),
				"name": ("!=", self.name),
			},
		)
		if existing:
			frappe.throw(
				_("Physical tool {0} is already registered under {1}.").format(
					self.physical_tool_code, existing
				)
			)

	def set_item_codes(self):
		for row in self.conditions:
			suffix = frappe.db.get_value("TMS Tool Condition", row.tool_condition, "item_code_suffix")
			row.item_code = "{0}{1}".format(self.physical_tool_code, suffix or "")
			if row.serialised:
				row.serial_no_series = "{0}-.####".format(row.item_code)
			else:
				row.serial_no_series = None

	@frappe.whitelist()
	def fetch_conditions(self):
		"""Populate the condition table from the Tool Condition master."""
		tool_type = frappe.db.get_value(
			"TMS Tool Type", self.tool_type, ["is_regrindable"], as_dict=True
		)
		is_regrindable = tool_type and tool_type.is_regrindable

		filters = {}
		if not is_regrindable:
			filters["is_regrind_input"] = 0

		conditions = frappe.get_all(
			"TMS Tool Condition",
			filters=filters,
			fields=["name", "serialised", "is_regrind_output"],
			order_by="sort_order asc",
		)

		self.set("conditions", [])
		for condition in conditions:
			if not is_regrindable and condition.is_regrind_output:
				continue
			self.append("conditions", {"tool_condition": condition.name})

		self.set_item_codes()
		return len(self.conditions)

	def before_submit(self):
		if not self.conditions:
			frappe.throw(_("At least one tool condition is required before registering the tool."))

	def on_submit(self):
		created = self.create_items()
		self.db_set("registration_status", "Registered")
		frappe.msgprint(
			_("Registered physical tool {0}. {1} item code(s) created.").format(
				self.physical_tool_code, created
			),
			indicator="green",
			alert=True,
		)

	def create_items(self):
		created = 0
		for row in self.conditions:
			if frappe.db.exists("Item", row.item_code):
				row.db_set("created", 1)
				continue

			condition = frappe.get_cached_doc("TMS Tool Condition", row.tool_condition)
			item = frappe.new_doc("Item")
			item.item_code = row.item_code
			item.item_name = "{0} - {1}".format(
				self.tool_description or self.tool_type, condition.condition_name
			)
			item.description = self.tool_description or self.tool_type
			item.item_group = self.item_group
			item.stock_uom = self.stock_uom
			item.is_stock_item = 1
			item.include_item_in_manufacturing = 0
			item.is_purchase_item = 1 if condition.condition_code == "N" else 0
			item.is_sales_item = 0

			if condition.serialised:
				item.has_serial_no = 1
				item.serial_no_series = row.serial_no_series

			hsn = self.gst_hsn_code or frappe.db.get_single_value(
				"TMS Settings", "default_hsn_code"
			)
			if hsn and item.meta.has_field("gst_hsn_code"):
				item.gst_hsn_code = hsn

			item.tms_is_tool = 1
			item.tms_tool_type = self.tool_type
			item.tms_tool_condition = row.tool_condition
			item.tms_physical_tool_code = self.physical_tool_code
			item.insert(ignore_permissions=True)

			row.db_set("created", 1)
			created += 1

		return created

	def on_cancel(self):
		"""Items already carrying stock or transactions are never removed on cancel."""
		self.db_set("registration_status", "Cancelled")
		frappe.msgprint(
			_("Registration cancelled. Item codes already created were left in place; "
			  "disable them manually if they were created in error."),
			indicator="orange",
		)


@frappe.whitelist()
def get_condition_item(physical_tool_code, condition_code):
	"""Resolve the item code for a physical tool in a given condition."""
	suffix = frappe.db.get_value("TMS Tool Condition", condition_code, "item_code_suffix")
	if suffix is None:
		frappe.throw(_("Tool Condition {0} does not exist.").format(condition_code))

	item_code = "{0}{1}".format(physical_tool_code, suffix)
	if not frappe.db.exists("Item", item_code):
		frappe.throw(
			_("Item {0} does not exist. Register the tool for condition {1} first.").format(
				item_code, condition_code
			)
		)
	return item_code
