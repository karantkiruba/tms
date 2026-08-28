//$(window).on('hashchange', page_changed);
//$(window).on('load', page_changed);
//$(function() {
//	$('.dropdown-help').hide();  // or .remove();
//});
//function page_changed(event) {
  //      frappe.after_ajax(function () {
                var route = frappe.get_route();
                if (route && route[0] == "Form") {
                        frappe.ui.form.on(route[1], {
                               onload: function (cur_frm,cdt,cdn) {
					console.log(cur_frm)
					 if(cur_frm.get_docfield('naming_series_definition'))
					  {if(cur_frm.doc.naming_series_definition && cur_frm.doc.creation != undefined) return;}
					 //{if(cur_frm.doc.naming_series_definition) return;}
                                          if(cur_frm.get_docfield('naming_series_definition')&& frappe.session.user !== 'Administrator'&& cur_frm.doc.creation === undefined){
                                                 cur_frm.set_df_property("naming_series", "read_only", 1);
                                                frappe.call({
                                                    method: "frappe.client.get",
                                                    args: {
                                                    doctype: 'Naming Series Manager',
                                                    filters: {"allow":cur_frm.doc.doctype,"username":frappe.session.user}
                                                    },
                                                    callback(r) {
                                                        console.log(r);
                                                        frappe.call({
                                                            method: "frappe.client.get",
                                                            args: {
                                                            doctype: 'Naming Series Manager',
                                                            name:r.message.document_name
                                                            },
                                                            callback(r) {
                                                                if(r.message) {
                                                                    var task = r.message;
                                                                    var newoption = new Array();
                                                                    var newoption1 = new Array();
                                                                    frappe.call({
                                                                        //method: "frappe.client.get",
                                                                        "method": "spokes_sgt.naming_series_manager.get_series_definition_list",
                                                                        args: {
                                                                           // doctype: "Naming Series Definition",
                                                                           // name:route[1]
                                                                           doctype:route[1]
                                                                        },
                                                                        callback: function (ret){
                                                                            var define=ret;
									   //if(frm.get_docfield('unit_doc_type')&& frappe.session.user !== 'Administrator'&& frm.doc.creation === undefined)
									   //{
									//	frm.set_value('unit_doc_type',task.name)
                                                                          // }
									    for(var i=0;i<task.series_list.length;i++)
                                                                            {
                                                                                if(task.series_list[i].ischecked === 1)
                                                                                {
                                                                                    for(var j=0;j<define.message.length;j++)
                                                                                    {
                                                                                        if(define.message[j].series_name === task.series_list[i].series_name){
                                                                                            newoption1.push(define.message[j].definition);
                                                                                            newoption.push(task.series_list[i].series_name);
                                                                                        }
                                                                                    }
                                                                                }
                                                                                if(task.series_list[i].isdefault === 1)
                                                                                {
//                                                                                    newoption=new Array();
//                                                                                    newoption1=new Array();
                                                                                    for(var j=0;j<ret.message.length;j++)
                                                                                    {
                                                                                        if(ret.message[j].series_name === task.series_list[i].series_name){
                                                                                              cur_frm.set_value('naming_series_definition', ret.message[j].definition)
//                                                                                            newoption1.push(ret.message.series_list_definition[j].definition);
//                                                                                            newoption.push(task.series_list[i].series_name);
 
                                                                                            break;
                                                                                        }
                                                                                    }
                                                                                }
                                                                            }
                                                                            cur_frm.set_df_property('naming_series_definition', 'options', newoption1);
                                                                            cur_frm.set_df_property('naming_series', 'options', newoption);
                                                                        }
                                                                    })
                                                                }
                                                            }
                                                        });
                                                    }
                                                });
                                            }
                                            if(cur_frm.get_docfield('naming_series_definition')&& frappe.session.user === 'Administrator'&& cur_frm.doc.creation === undefined){
                                                cur_frm.set_df_property("naming_series", "read_only", 1);
                                                var newoption1 = new Array();
                                                frappe.call({
                                                    //method: "frappe.get_doc",
                                                   "method": "spokes_sgt.naming_series_manager.get_series_definition_list",
                                                    args: {
                                                        //doctype: "Naming Series Definition",
                                                        //name:route[1]
                                                        doctype: route[1] 
                                                   },
                                                        callback: function (ret){
                                                            var define=ret;
                                                            for(var j=0;j<define.message.length;j++)
                                                            {
                                                                newoption1.push(define.message[j].definition);
                                                            }
                                                            cur_frm.set_df_property('naming_series_definition', 'options', newoption1);
                                                    }
                                                });
                                            }
                                },
                                naming_series_definition:function(cur_frm,cdt,cdn){
                                    if(cur_frm.get_docfield('naming_series_definition') && cur_frm.doc.naming_series_manager !== '' && cur_frm.doc.naming_series_definition !== ''){
                                        frappe.call({
                                            //method: "frappe.get_doc",
                                            "method": "spokes_sgt.naming_series_manager.get_series_definition_list",
                                            args: {
                                                //doctype: "Naming Series Definition",
                                                //name:route[1]
                                                doctype: route[1] 
                                           },
                                            callback: function (ret){
                                                var def=ret;
						//if(frm.get_docfield('unit_doc_type')&& frm.doc.naming_series_manager !== '' && frm.doc.naming_series_definition !== '')
                                                //{
                                                 //  frm.set_value('unit_doc_type',def.name)
                                                //}
                                                for(var j=0;j<def.message.length;j++)
                                                {
                                                    if(def.message[j].definition === cur_frm.doc.naming_series_definition){
                                                        cur_frm.set_value('naming_series', def.message[j].series_name)

                                                    if(def.message[j].company)
                                                    {
                                                        cur_frm.set_value('company', def.message[j].company)
                                                    }
							if(def.message[j].cost_center)
                                                    {
                                                        cur_frm.set_value('cost_center', def.message[j].cost_center)
                                                    }
							                                                    if(def.message[j].unit_type){
                                                        if(cur_frm.doc.doctype === "Transfer Out"){
                                                                 cur_frm.set_value('from_branch', def.message[j].unit_type)
                                                        }else{
                                                        cur_frm.set_value('branch', def.message[j].unit_type)
                                                        }
                                                    }
						if (def.message[j].source_warehouse) {

    if (
        cur_frm.doc.doctype === "Transfer Out" ||
        cur_frm.doc.doctype === "Sales Invoice" ||
        cur_frm.doc.doctype === "Purchase Invoice" ||
        cur_frm.doc.doctype === "Delivery Note" ||
        cur_frm.doc.doctype === "Purchase Order" ||
        cur_frm.doc.doctype === "Purchase Receipt" ||
        cur_frm.doc.doctype === "Material Request"
    ) {

        cur_frm.set_value(
            "set_warehouse",
            def.message[j].source_warehouse
        );

    } else if (cur_frm.doc.doctype === "TMS Used Tool Inspection") {

        cur_frm.set_value(
            "used_tool_warehouse",
            def.message[j].source_warehouse
        );

    } else {

        cur_frm.set_value(
            "source_warehouse",
            def.message[j].source_warehouse
        );
    }
}
							  if(def.message[j].company_address)
                                                    {
							if(cur_frm.doc.doctype === "Sales Invoice" || cur_frm.doc.doctype === "Delivery Note" || cur_frm.doc.doctype === "Sales Order"){
                                                        cur_frm.set_value('company_address', def.message[j].company_address)
							}
							 if(cur_frm.doc.doctype === "Purchase Invoice" ||  cur_frm.doc.doctype === "Purchase Order" || cur_frm.doc.doctype === "Purchase Receipt"){
                                                        cur_frm.set_value('billing_address', def.message[j].company_address)
							 cur_frm.set_value('shipping_address', def.message[j].company_address)
                                                        }

                                                    }

if (def.message[j].target_warehouse) {

    if (cur_frm.doc.doctype === "Transfer Out") {

        cur_frm.set_value(
            "target_warehouse",
            def.message[j].target_warehouse
        );

    } else if (cur_frm.doc.doctype === "TMS Used Tool Inspection") {

        cur_frm.set_value(
            "main_warehouse",
            def.message[j].target_warehouse
        );

    } else if (cur_frm.doc.doctype === "Work Order") {

        cur_frm.set_value(
            "fg_warehouse",
            def.message[j].target_warehouse
        );

    } else {

        cur_frm.set_value(
            "target_warehouse",
            def.message[j].target_warehouse
        );
    }
}							if(def.message[j].work_in_progress_warehouse){
                                                                 if(cur_frm.doc.doctype === "Work Order"){
                                                                        cur_frm.set_value('wip_warehouse', def.message[j].work_in_progress_warehouse)
                                                                        }
                                                        }

                                                         if(def.message[j].to_branch){
                                                                 if(cur_frm.doc.doctype === "Transfer Out"){
                                                                        cur_frm.set_value('to_branch', def.message[j].to_branch)
                                                                        }
                                                        }

                                                        if(def.message[j].transfer_out_location){
                                                                 
                                                                        cur_frm.set_value('transfer_out_location', def.message[j].transfer_out_location)
                                                        }


                                                    }

                                                } 
                                            }
                                        })
                                    }
                                }
                        })
                }
    //    })
//}
