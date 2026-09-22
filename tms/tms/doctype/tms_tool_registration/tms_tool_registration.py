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
		self.validate_regrind_settings()
		self.validate_life()

	def validate_regrind_settings(self):
		if not self.is_regrindable:
			self.max_regrind_count = 0
			self.planned_reground_tool_life = 0
			self.standard_regrind_cost = 0
			return

		if not self.max_regrind_count or self.max_regrind_count < 1:
			frappe.throw(_("Maximum Regrind Count must be at least 1 for a regrindable tool type."))

	@frappe.whitelist()
	def refresh_purchase_cost(self):
		"""Pull the actual purchase cost for this tool type from receipt history."""
		from tms.utils.costing import update_tool_type_cost

		cost = update_tool_type_cost(self.name)
		self.reload()
		return cost

	def validate_life(self):
		for field in ("planned_new_tool_life", "planned_reground_tool_life"):
			if (self.get(field) or 0) < 0:
				frappe.throw(_("{0} cannot be negative.").format(_(self.meta.get_label(field))))

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
		#tool_type = frappe.db.get_value(
		#	"TMS Tool Type", self.tool_type, ["is_regrindable"], as_dict=True
		#)
		#is_regrindable = tool_type and tool_type.is_regrindable

		#filters = {}
		#if not is_regrindable:
		#	filters["is_regrind_input"] = 0

		conditions = frappe.get_all(
			"TMS Tool Condition",
			fields=["name", "serialised", "is_regrind_output"],
			order_by="sort_order asc",
		)

		self.set("conditions", [])
		for condition in conditions:
			#if not is_regrindable and condition.is_regrind_output:
			#	continue
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
			item.include_item_in_manufacturing = 1
			item.is_purchase_item = 1 if condition.condition_code == "N" else 0
			item.is_sales_item = 1
			if condition.condition_name in ["Regrinding Pending", "Regrinding Finished"]:
				item.valuation_rate = self.standard_regrind_cost
				item.bin = self.rg_location
			elif condition.condition_name == "New":
				item.valuation_rate = self.standard_new_tool_cost
				item.bin = self.new_location
			else:
				item.valuation_rate = 0
			#item.valuation_rate = self.standard_new_tool_cost
			#item.valuation_rate = self.standard_regrind_cost if condition.condition_name in ["Regrinding Pending", "Regrinding Finished"] else self.standard_new_tool_cost
			item.custom_is_regrindable = self.is_regrindable

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
			item.custom_tms_tool_registration = self.name
			item.tms_physical_tool_code = self.physical_tool_code
			item.brand = self.make
			item.append("taxes", {
				"item_tax_template": "GST 18% - UTM",
				"tax_category": "In-State"
			})
			item.append("taxes", {
				"item_tax_template": "GST 18% - UTM",
				"tax_category": "Out-State"
			})
			item.insert(ignore_permissions=True)
			if condition.condition_name == "Regrinding Finished":
				frappe.db.set_value("Item",item.name,"is_sub_contracted_item",1)
				pending_condition = frappe.db.get_value(
						"TMS Tool Condition",
						{"condition_name": "Regrinding Pending"},
						"name"
				)

				pending_item = frappe.db.get_value(
						"Item",{"tms_tool_type": self.tool_type,"tms_tool_condition": pending_condition},"name")

				if pending_item:
					#frappe.db.set_value("Item",pending_item,"is_sub_contracted_item",1)

					if not frappe.db.exists("BOM",{"item": item.item_code,"is_active": 1,"is_default": 1}):
						bom = frappe.new_doc("BOM")
						bom.item = item.item_code
						bom.quantity = 1
						bom.is_active = 1
						bom.is_rgf = 1

						bom.append("items", {
							"item_code": item.item_code,
							"qty": 1,
							"do_not_explode": 1,
							"uom": self.stock_uom
						})

						bom.insert(ignore_permissions=True)
						bom.submit()

						bom = frappe.new_doc("BOM")
						bom.item = item.item_code
						bom.quantity = 1
						bom.is_active = 1
						bom.is_default = 1
						bom.append("items", {
							"item_code":pending_item,
							"qty": 1,
							#"do_not_explode": 1,
							"uom": self.stock_uom
						})
						bom.insert(ignore_permissions=True)
						bom.submit()
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
