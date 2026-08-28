
import frappe
from frappe.utils import cint

@frappe.whitelist()
def get_cpc_component_operation(cpc_component):
    rows = frappe.get_all(
        "CPC Component Operation",
        filters={
            "parent": cpc_component,
            "parenttype": "CPC Component"
        },
        fields=["machine", "operation", "production_line"],
        order_by="idx asc"
    )

    return rows


@frappe.whitelist()
def update_regrind_cycle(doc, method=None):
    for row in doc.items:

        if not row.serial_no:
            continue

        # serial_no can contain multiple serial numbers
        serial_nos = [x.strip() for x in row.serial_no.split("\n") if x.strip()]

        for serial_no in serial_nos:

            current_cycle = frappe.db.get_value(
                "Serial No",
                serial_no,
                "tms_regrind_cycle"
            )

            new_cycle = cint(current_cycle) + 1

            frappe.db.set_value(
                "Serial No",
                serial_no,
                "tms_regrind_cycle",
                new_cycle
            )
