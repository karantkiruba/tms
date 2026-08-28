# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from tms.utils import stock as stock_utils
from tms.utils import validation as tms_validate
from tms.tms.doctype.tms_tool_registration.tms_tool_registration import get_condition_item


class TMSRegrindCycle(Document):
	"""One regrinding cycle for one physical tool (BRS sections 27 to 30).

	Submitting the cycle converts the incoming condition item into Regrinding
	Pending. Completing it converts RGP into Regrinding Finished and issues a new
	serial carrying the completed regrind count, so the count only ever moves on
	a successful, inspected completion (rule 17).
	"""

	def validate(self):
		self.resolve_condition_items()
		self.set_regrind_counts()

	def resolve_condition_items(self):
		self.rgp_item = get_condition_item(self.physical_tool_code, "RGP")
		self.rgf_item = get_condition_item(self.physical_tool_code, "RGF")
		self.rej_item = get_condition_item(self.physical_tool_code, "REJ")

	def set_regrind_counts(self):
		tool_type = frappe.db.get_value(
			"TMS Tool Registration", self.tool_registration, ["is_regrindable", "max_regrind_count",
			                                  "standard_regrind_cost"], as_dict=True
		)
		if not tool_type or not tool_type.is_regrindable:
			frappe.throw(_("Tool Type {0} is not regrindable.").format(self.tool_type))

		self.max_regrind_count = tool_type.max_regrind_count
		self.completed_regrind_count = tms_validate.get_serial_regrind_cycle(self.source_serial_no)

		if self.status in ("Draft", "Pending Regrinding"):
			self.cycle_number = self.completed_regrind_count + 1

		self.remaining_regrinds = flt(self.max_regrind_count) - flt(self.completed_regrind_count)

		if not self.regrind_cost:
			self.regrind_cost = tool_type.standard_regrind_cost

	def before_submit(self):
		"""Rule 18: the maximum is validated before a new cycle starts, not after."""
		tms_validate.validate_regrind_capacity(self.source_item, self.source_serial_no)

	def on_submit(self):
		#self.convert_to_rgp()
		self.db_set("status", "Pending Regrinding")

	def convert_to_rgp(self):
		"""Consume the incoming condition item and produce Regrinding Pending.

		The completed regrind count deliberately does not move here (rule 17).
		"""
		consume = [{"item_code": self.source_item, "qty": flt(self.qty) or 1,
		            "serial_no": self.source_serial_no}]
		produce = [{"item_code": self.rgp_item, "qty": flt(self.qty) or 1}]

		entry = stock_utils.make_repack(self, consume, produce, self.ho_warehouse)
		self.db_set("rgp_stock_entry", entry)
		self.db_set("status", "Pending Regrinding")

	#@frappe.whitelist()
	def complete_regrind(self, inspection_result=None, regrind_cost=None,completed_qty=None):
		"""Convert RGP to RGF, issue the next-cycle serial and move the count."""
		if self.docstatus != 1:
			frappe.throw(_("Submit the regrind cycle before completing it."))
		if self.status != "Pending Regrinding":
			frappe.throw(_("This cycle is {0}, not Pending Regrinding.").format(self.status))

		if completed_qty is None:
			frappe.throw(_("Please enter Completed Qty."))

		completed_qty = flt(completed_qty)

		if completed_qty <= 0:
			frappe.throw(_("Completed Qty must be greater than zero."))

		if completed_qty > flt(self.qty):
			frappe.throw(
				_("Completed Qty {0} cannot be greater than Cycle Qty {1}.")
				.format(completed_qty, self.qty)
			)

		result = inspection_result or self.inspection_result
		if result not in ("Accepted", "Rejected"):
			frappe.throw(_("Record the inspection result as Accepted or Rejected."))

		if regrind_cost is not None:
			self.db_set("regrind_cost", flt(regrind_cost))

		if result == "Rejected":
			return self._complete_as_rejected(completed_qty)
		return self._complete_as_reground(completed_qty)

	def _complete_as_reground(self,completed_qty):
		completed_qty = int(completed_qty)

		serial_numbers = []

		for i in range(completed_qty):
			serial_no = stock_utils.generate_serial_no(self.rgf_item)
			serial_numbers.append(serial_no)

		serial_no_string = "\n".join(serial_numbers)

		consume = [{"item_code": self.rgp_item, "qty": completed_qty or 1}]
		produce = [{"item_code": self.rgf_item, "qty": completed_qty,
		            "serial_no": serial_no_string}]

		entry = stock_utils.make_repack(
			self, consume, produce, self.ho_warehouse,
			additional_cost=flt(self.regrind_cost),
			cost_description=_("Regrinding charges for {0}").format(self.physical_tool_code),
		)
		for serial_no in serial_numbers:
			self.stamp_serial(serial_no)

		self.db_set("rgf_stock_entry", entry)
		self.db_set("output_serial_no", serial_no_string)
		self.db_set("inspection_result", "Accepted")
		self.db_set("completed_regrind_count", self.cycle_number)
		self.db_set("remaining_regrinds", flt(self.max_regrind_count) - flt(self.cycle_number))
		self.db_set("status", "Completed")

		frappe.msgprint(
			_("Regrind cycle {0} completed. {1} issued at regrind count {2} of {3}.").format(
				self.cycle_number, serial_no, self.cycle_number,completed_qty, self.max_regrind_count
			),
			indicator="green", alert=True,
		)
		return serial_no_string

	def stamp_serial(self, serial_no):
		"""Carry the tool's identity and cycle onto the new serial.

		A Serial No is bound to its item code, so it cannot survive the condition
		conversion. The cycle number and the previous serial are written here to
		keep the chain intact across item codes.
		"""
		frappe.db.set_value("Serial No", serial_no, {
			"tms_tool_type": self.tool_type,
			"tms_physical_tool_code": self.physical_tool_code,
			"tms_regrind_cycle": self.cycle_number,
			"tms_previous_serial_no": self.source_serial_no,
			"tms_last_cpc_component": self.cpc_component_last_used,
		}, update_modified=False)

	def _complete_as_rejected(self):
		"""A failed regrind converts to the rejected item and never moves the count."""
		consume = [{"item_code": self.rgp_item, "qty": flt(self.qty) or 1}]
		produce = [{"item_code": self.rej_item, "qty": flt(self.qty) or 1}]

		entry = stock_utils.make_repack(self, consume, produce, self.ho_warehouse)

		self.db_set("rgf_stock_entry", entry)
		self.db_set("inspection_result", "Rejected")
		self.db_set("status", "Rejected")

		frappe.msgprint(
			_("Regrind cycle {0} rejected. Stock converted to {1}; the regrind count is unchanged.").format(
				self.cycle_number, self.rej_item
			),
			indicator="orange", alert=True,
		)
		return None

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Stock Entry", "Stock Ledger Entry", "GL Entry")
		for field in ("rgf_stock_entry", "rgp_stock_entry"):
			entry = self.get(field)
			if entry and frappe.db.exists("Stock Entry", entry):
				se = frappe.get_doc("Stock Entry", entry)
				if se.docstatus == 1:
					se.flags.ignore_permissions = True
					se.cancel()
		self.db_set("status", "Cancelled")


@frappe.whitelist()
def get_regrind_status(physical_tool_code):
	"""Regrind position of one physical tool, for the section 45.4 reports."""
	cycles = frappe.get_all(
		"TMS Regrind Cycle",
		filters={"physical_tool_code": physical_tool_code, "docstatus": 1},
		fields=["name", "cycle_number", "status", "output_serial_no", "regrind_cost"],
		order_by="cycle_number asc",
	)
	completed = [c for c in cycles if c.status == "Completed"]
	max_count = frappe.db.get_value(
		"TMS Tool Type",
		frappe.db.get_value("TMS Regrind Cycle", {"physical_tool_code": physical_tool_code},
		                    "tool_type"),
		"max_regrind_count",
	) or 0

	return {
		"physical_tool_code": physical_tool_code,
		"cycles": cycles,
		"completed_regrind_count": len(completed),
		"max_regrind_count": max_count,
		"remaining_regrinds": max_count - len(completed),
	}

@frappe.whitelist()
def complete_regrind(docname, inspection_result=None, regrind_cost=None, completed_qty=None):
    doc = frappe.get_doc("TMS Regrind Cycle", docname)

    return doc.complete_regrind(
        inspection_result=inspection_result,
        regrind_cost=regrind_cost,
        completed_qty=completed_qty
    )
