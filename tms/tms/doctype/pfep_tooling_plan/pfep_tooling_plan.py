# Copyright (c) 2026, Spokes and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class PFEPToolingPlan(Document):
	def validate(self):
		self.validate_dates()
		self.validate_component()
		self.validate_rows()
		self.validate_primary_tool()

	def validate_dates(self):
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be earlier than Effective From."))

	def validate_component(self):
		component = frappe.db.get_value(
			"CPC Component", self.cpc_component, ["tms_location", "customer"], as_dict=True
		)
		if not component:
			return
		if component.tms_location != self.tms_location:
			frappe.throw(
				_("CPC Component {0} belongs to TMS Location {1}, not {2}.").format(
					self.cpc_component, component.tms_location, self.tms_location
				)
			)
		if component.customer != self.customer:
			frappe.throw(
				_("CPC Component {0} belongs to Customer {1}, not {2}.").format(
					self.cpc_component, component.customer, self.customer
				)
			)

	def validate_rows(self):
		if not self.tools:
			frappe.throw(_("At least one PFEP tool row is required."))

		component = frappe.get_cached_doc("CPC Component", self.cpc_component)
		for row in self.tools:
			if not component.is_valid_machine_operation(row.machine, row.operation):
				frappe.throw(
					_("Row {0}: Machine {1} with Operation {2} is not defined on CPC Component {3}.").format(
						row.idx, row.machine, row.operation, self.cpc_component
					)
				)

	def validate_primary_tool(self):
		primary = [r for r in self.tools if r.is_primary_tool]
		by_operation = {}
		for row in primary:
			by_operation.setdefault((row.machine, row.operation), []).append(row.idx)

		for key, rows in by_operation.items():
			if len(rows) > 1:
				frappe.msgprint(
					_("Machine {0} Operation {1} has more than one primary tool (rows {2}). "
					  "Tool life is measured against a single primary tool.").format(
						key[0], key[1], ", ".join(str(r) for r in rows)
					)
				)

	def before_submit(self):
		self.validate_no_overlap()
		self.status = "Approved"
		if not self.approved_by:
			self.approved_by = frappe.session.user

	def validate_no_overlap(self):
		"""Only one approved PFEP may be effective for a component at any date."""
		overlapping = frappe.db.sql(
			"""
			select name, effective_from, effective_to
			from `tabPFEP Tooling Plan`
			where cpc_component = %(component)s
			  and docstatus = 1
			  and status = 'Approved'
			  and name != %(name)s
			  and (
			      %(from)s between effective_from and ifnull(effective_to, '2999-12-31')
			      or ifnull(%(to)s, '2999-12-31') between effective_from and ifnull(effective_to, '2999-12-31')
			      or effective_from between %(from)s and ifnull(%(to)s, '2999-12-31')
			  )
			""",
			{
				"component": self.cpc_component,
				"name": self.name,
				"from": self.effective_from,
				"to": self.effective_to,
			},
			as_dict=True,
		)
		if overlapping:
			frappe.throw(
				_("PFEP {0} is already approved for {1} over an overlapping period. "
				  "Supersede it before approving this plan.").format(
					overlapping[0].name, self.cpc_component
				)
			)

	def on_cancel(self):
		self.status = "Cancelled"

	@frappe.whitelist()
	def create_revision(self, change_reason=None):
		"""Approved PFEP is never edited. This supersedes it and returns a new draft revision."""
		if self.docstatus != 1:
			frappe.throw(_("Only an approved PFEP can be revised."))

		new = frappe.copy_doc(self)
		new.revision_number = (self.revision_number or 0) + 1
		new.previous_pfep = self.name
		new.status = "Draft"
		new.approved_by = None
		new.amended_from = None
		new.append(
			"revisions",
			{
				"revision_number": new.revision_number,
				"effective_date": new.effective_from,
				"change_reason": change_reason,
				"changed_by": frappe.session.user,
			},
		)
		new.insert()

		self.db_set("status", "Superseded")
		return new.name


def get_active_pfep(cpc_component, posting_date=None):
	"""Return the approved PFEP effective for a component on a date."""
	posting_date = posting_date or frappe.utils.nowdate()
	rows = frappe.db.sql(
		"""
		select name
		from `tabPFEP Tooling Plan`
		where cpc_component = %(component)s
		  and docstatus = 1
		  and status = 'Approved'
		  and effective_from <= %(date)s
		  and ifnull(effective_to, '2999-12-31') >= %(date)s
		order by effective_from desc
		limit 1
		""",
		{"component": cpc_component, "date": posting_date},
	)
	return rows[0][0] if rows else None
