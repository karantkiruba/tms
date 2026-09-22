
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

	def validate(self):
		self.resolve_condition_items()
		self.validate_regrind_detail_rows()
		self.set_regrind_counts()

	def resolve_condition_items(self):
		self.rgp_item = get_condition_item(
			self.physical_tool_code,
			"RGP"
		)

		self.rgf_item = get_condition_item(
			self.physical_tool_code,
			"RGF"
		)

		self.rej_item = get_condition_item(
			self.physical_tool_code,
			"REJ"
		)

	def validate_regrind_detail_rows(self):

		qty = int(flt(self.qty))

		if qty <= 0:
			frappe.throw(
				_("Qty must be greater than zero.")
			)

		if len(self.regrind_count_detail) != qty:
			frappe.throw(
				_(
					"Qty is {0}, but Regrind Count Detail has {1} row(s). "
					"Please create exactly {0} row(s)."
				).format(
					qty,
					len(self.regrind_count_detail)
				)
			)

	def set_regrind_counts(self):

		tool_info = frappe.db.get_value(
			"TMS Tool Registration",
			self.tool_registration,
			[
				"is_regrindable",
				"max_regrind_count",
				"standard_regrind_cost"
			],
			as_dict=True
		)

		if not tool_info:
			frappe.throw(
				_("Tool Registration {0} not found.").format(
					self.tool_registration
				)
			)

		if not tool_info.is_regrindable:
			frappe.throw(
				_("Tool Type {0} is not regrindable.").format(
					self.tool_type
				)
			)

		max_regrind_count = flt(
			tool_info.max_regrind_count
		)

		for row in self.regrind_count_detail:

			incoming_serial_no = row.incoming_serial_no

			completed_count = tms_validate.get_serial_regrind_cycle(
				incoming_serial_no
			)

			this_cycle = completed_count + 1

			if not incoming_serial_no:
				completed_count = 0
				this_cycle = 1

			row.this_cycle_number = this_cycle
			row.completed_regrind_count = completed_count
			row.maximum_regrind_count = max_regrind_count
			row.remaining_regrinds = (
				max_regrind_count - completed_count
			)

		if not self.regrind_cost:
			self.regrind_cost = flt(
				tool_info.standard_regrind_cost
			)

	def before_submit(self):

		for row in self.regrind_count_detail:

			if row.incoming_serial_no:

				tms_validate.validate_regrind_capacity(
					self.source_item,
					row.incoming_serial_no
				)

	def on_submit(self):

		self.db_set(
			"status",
			"Pending Regrinding"
		)

	def convert_to_rgp(self):

		consume = [{
			"item_code": self.source_item,
			"qty": flt(self.qty) or 1,
			"serial_no": self.source_serial_no
		}]

		produce = [{
			"item_code": self.rgp_item,
			"qty": flt(self.qty) or 1
		}]

		entry = stock_utils.make_repack(
			self,
			consume,
			produce,
			self.ho_warehouse
		)

		self.db_set(
			"rgp_stock_entry",
			entry
		)

		self.db_set(
			"status",
			"Pending Regrinding"
		)

	def complete_regrind(
		self,
		inspection_result=None,
		regrind_cost=None,
		completed_qty=None
	):

		if self.docstatus != 1:
			frappe.throw(
				_("Submit the regrind cycle before completing it.")
			)

		if self.status != "Pending Regrinding":
			frappe.throw(
				_("This cycle is {0}, not Pending Regrinding.").format(
					self.status
				)
			)

		if completed_qty is None:
			frappe.throw(
				_("Please enter Completed Qty.")
			)

		completed_qty = int(flt(completed_qty))

		if completed_qty <= 0:
			frappe.throw(
				_("Completed Qty must be greater than zero.")
			)

		if completed_qty > int(flt(self.qty)):
			frappe.throw(
				_(
					"Completed Qty {0} cannot be greater than Cycle Qty {1}."
				).format(
					completed_qty,
					self.qty
				)
			)

		result = (
			inspection_result
			or self.inspection_result
		)

		if result not in ("Accepted", "Rejected"):
			frappe.throw(
				_("Record the inspection result as Accepted or Rejected.")
			)

		if regrind_cost is not None:

			self.db_set(
				"regrind_cost",
				flt(regrind_cost)
			)

		if result == "Rejected":

			return self._complete_as_rejected(
				completed_qty
			)

		return self._complete_as_reground(
			completed_qty
		)

	def _complete_as_reground(self, completed_qty):

		completed_qty = int(completed_qty)

		available_rows = []

		for row in self.regrind_count_detail:

			if not row.reground_serial_no:

				available_rows.append(row)

		if completed_qty > len(available_rows):

			frappe.throw(
				_(
					"Completed Qty {0} cannot be greater than "
					"available Regrind Count Detail rows {1}."
				).format(
					completed_qty,
					len(available_rows)
				)
			)

		serial_numbers = []

		for index in range(completed_qty):

			detail_row = available_rows[index]

			incoming_serial_no = detail_row.incoming_serial_no

			if incoming_serial_no:
				serial_no = incoming_serial_no
			else:
				serial_no = stock_utils.generate_serial_no(
					self.rgf_item
				)

			serial_numbers.append(
				serial_no
			)

		serial_no_string = "\n".join(
			serial_numbers
		)

		consume = [{
			"item_code": self.rgp_item,
			"qty": completed_qty
		}]

		produce = [{
			"item_code": self.rgf_item,
			"qty": completed_qty,
			"set_basic_rate_manually":1,
			"basic_rate": flt(self.regrind_cost),
			"serial_no": serial_no_string
		}]

		entry = stock_utils.make_repack(
			self,
			consume,
			produce,
			self.ho_warehouse
			#additional_cost=flt(
			#	self.regrind_cost
			#),
			#cost_description=_(
			#	"Regrinding charges for {0}"
			#).format(
			#	self.physical_tool_code
			#)
		)

		for index, serial_no in enumerate(serial_numbers):

			detail_row = available_rows[index]

			incoming_serial_no = (
				detail_row.incoming_serial_no
			)

			current_completed_count = flt(
				detail_row.completed_regrind_count
			)

			maximum_regrind_count = flt(
				detail_row.maximum_regrind_count
			)

			new_completed_count = (
				current_completed_count + 1
			)

			detail_row.db_set(
				"reground_serial_no",
				serial_no,
				update_modified=False
			)

			detail_row.db_set(
				"this_cycle_number",
				new_completed_count,
				update_modified=False
			)

			detail_row.db_set(
				"completed_regrind_count",
				new_completed_count,
				update_modified=False
			)

			detail_row.db_set(
				"remaining_regrinds",
				maximum_regrind_count - new_completed_count,
				update_modified=False
			)

			self.stamp_serial(
				serial_no,
				incoming_serial_no,
				new_completed_count
			)

		self.db_set(
			"rgf_stock_entry",
			entry
		)

		self.db_set(
			"output_serial_no",
			serial_no_string
		)

		self.db_set(
			"inspection_result",
			"Accepted"
		)

		self.db_set(
			"status",
			"Completed"
		)

		frappe.msgprint(
			_(
				"Regrinding completed successfully. "
				"{0} serial number(s) generated."
			).format(
				completed_qty
			),
			indicator="green",
			alert=True
		)

		return serial_no_string

	def stamp_serial(
		self,
		serial_no,
		previous_serial_no=None,
		regrind_cycle=None
	):

		frappe.db.set_value(
			"Serial No",
			serial_no,
			{
				"tms_tool_type":
					self.tool_type,

				"tms_physical_tool_code":
					self.physical_tool_code,

				"tms_regrind_cycle":
					regrind_cycle,

				"tms_previous_serial_no":
					previous_serial_no,

				"tms_last_cpc_component":
					self.cpc_component_last_used,
			},
			update_modified=False
		)

	def _complete_as_rejected(self, completed_qty):

		completed_qty = int(completed_qty)

		consume = [{
			"item_code": self.rgp_item,
			"qty": completed_qty
		}]

		produce = [{
			"item_code": self.rej_item,
			"qty": completed_qty
		}]

		entry = stock_utils.make_repack(
			self,
			consume,
			produce,
			self.ho_warehouse
		)

		self.db_set(
			"rgf_stock_entry",
			entry
		)

		self.db_set(
			"inspection_result",
			"Rejected"
		)

		self.db_set(
			"status",
			"Rejected"
		)

		frappe.msgprint(
			_(
				"Regrinding rejected. "
				"{0} quantity converted to {1}."
			).format(
				completed_qty,
				self.rej_item
			),
			indicator="orange",
			alert=True
		)

		return None

	def on_cancel(self):

		self.ignore_linked_doctypes = (
			"Stock Entry",
			"Stock Ledger Entry",
			"GL Entry"
		)

		for field in (
			"rgf_stock_entry",
			"rgp_stock_entry"
		):

			entry = self.get(field)

			if (
				entry
				and frappe.db.exists(
					"Stock Entry",
					entry
				)
			):

				se = frappe.get_doc(
					"Stock Entry",
					entry
				)

				if se.docstatus == 1:

					se.flags.ignore_permissions = True
					se.cancel()

		self.db_set(
			"status",
			"Cancelled"
		)


@frappe.whitelist()
def get_regrind_status(physical_tool_code):

	cycles = frappe.get_all(
		"TMS Regrind Cycle",
		filters={
			"physical_tool_code": physical_tool_code,
			"docstatus": 1
		},
		fields=[
			"name",
			"status",
			"output_serial_no",
			"regrind_cost"
		],
		order_by="creation asc"
	)

	return {
		"physical_tool_code": physical_tool_code,
		"cycles": cycles
	}


@frappe.whitelist()
def complete_regrind(
	docname,
	inspection_result=None,
	regrind_cost=None,
	completed_qty=None
):

	doc = frappe.get_doc(
		"TMS Regrind Cycle",
		docname
	)

	return doc.complete_regrind(
		inspection_result=inspection_result,
		regrind_cost=regrind_cost,
		completed_qty=completed_qty
	)
