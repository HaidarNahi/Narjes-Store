frappe.ui.form.on('Sales Order', {
    setup: function(frm) {
        // Dynamically bind to all Date and Datetime fields to update their weekday labels
        let date_fields = frm.meta.fields.filter(f => f.fieldtype === 'Date' || f.fieldtype === 'Datetime');
        let events = {};
        date_fields.forEach(df => {
            events[df.fieldname] = function(frm) {
                update_weekday_label(frm, df.fieldname);
            };
        });
        frappe.ui.form.on('Sales Order', events);

    },
    taxes_and_totals_calculated: function(frm) {
        // Hook natively provided by ERPNext to run after calculate_taxes_and_totals
        calculate_custom_totals(frm);
    },
    refresh: function(frm) {
        if (!frm.doc.__islocal) {
            render_custom_gallery(frm);
        }

        // Filter main items table to exclude flowers (and preserve standard ERPNext item query)
        frm.set_query("item_code", "items", function() {
            return {
                query: "erpnext.controllers.queries.item_query",
                filters: {
                    "is_sales_item": 1,
                    "has_variants": 0,
                    "custom_is_flower": 0
                }
            };
        });

        // Filter custom flower items table to ONLY include flowers
        frm.set_query("flower_item", "custom_flower_items", function() {
            return {
                filters: {
                    "custom_is_flower": 1
                }
            };
        });

        
        // Initialize weekday labels on load
        let date_fields = frm.meta.fields.filter(f => f.fieldtype === 'Date' || f.fieldtype === 'Datetime');
        date_fields.forEach(df => {
            update_weekday_label(frm, df.fieldname);
        });
        
        setTimeout(() => calculate_custom_totals(frm), 500);
    },
    governorate_of_delivery: function(frm) {
        setTimeout(() => calculate_custom_totals(frm), 500);
    },
    packaging_costs: function(frm) {
        setTimeout(() => calculate_custom_totals(frm), 500);
    },
    total: function(frm) {
        setTimeout(() => calculate_custom_totals(frm), 500);
    },
    additional_discount_percentage: function(frm) {
        setTimeout(() => calculate_custom_totals(frm), 500);
    },
    discount_amount: function(frm) {
        setTimeout(() => calculate_custom_totals(frm), 500);
    }
});

function update_weekday_label(frm, fieldname) {
    let $wrapper = frm.get_field(fieldname).$wrapper;
    if ($wrapper.find('.weekday-label').length === 0) {
        $wrapper.find('.control-input').after('<div class="weekday-label text-muted small" style="margin-top: 4px; font-weight: 600; color: #8D99A6;"></div>');
    }
    
    let val = frm.doc[fieldname];
    if (val) {
        moment.locale('ar-iq'); // Default to Arabic (Iraq)
        let weekdayName = moment(val).format('dddd');
        $wrapper.find('.weekday-label').text('(' + weekdayName + ')');
    } else {
        $wrapper.find('.weekday-label').text('');
    }
}

function calculate_custom_totals(frm) {
    if (frm.doc.docstatus !== 0) return;
    
    // 1. Calculate Delivery Fees based on Governorate.
    // Read live from Narjes Settings (exposed via frappe.boot.narjes_settings
    // — see extend_bootinfo in api.py) instead of hardcoding 4000/6000 here,
    // so this client-side preview can never silently drift from what an
    // admin has configured (see NARJES_STORE_SYSTEM.md §14.5/§14.6).
    let fee = 0;
    if (frm.doc.governorate_of_delivery) {
        let ns = (frappe.boot && frappe.boot.narjes_settings) || {};
        if (frm.doc.governorate_of_delivery === 'بغداد') {
            fee = ns.baghdad_delivery_fee || 0;
        } else {
            fee = ns.other_governorate_delivery_fee || 0;
        }
    }
    
    if (frm.doc.delivery_fees !== fee) {
        frappe.model.set_value(frm.doctype, frm.docname, 'delivery_fees', fee);
    }
    // Calculate Flower Total and Qty
    let flower_total = 0;
    let flower_qty = 0;
    (frm.doc.custom_flower_items || []).forEach(row => {
        flower_total += (row.amount || 0);
        flower_qty += (row.qty || 0);
    });

    if (frm.doc.custom_flower_total !== flower_total) {
        frappe.model.set_value(frm.doctype, frm.docname, 'custom_flower_total', flower_total);
    }
    
    // Refresh totals if needed
    frm.refresh_field('custom_flower_total');

    // Mutate Frappe standard total fields to include flowers (UI Only)
    let standard_total = frm.doc.items ? frm.doc.items.reduce((sum, row) => sum + (row.amount || 0), 0) : 0;
    let combined_total = standard_total + flower_total;
    
    let standard_qty = frm.doc.items ? frm.doc.items.reduce((sum, row) => sum + (row.qty || 0), 0) : 0;
    let combined_qty = standard_qty + flower_qty;

    if (frm.doc.total !== combined_total) {
        frappe.model.set_value(frm.doctype, frm.docname, 'total', combined_total);
        frappe.model.set_value(frm.doctype, frm.docname, 'net_total', combined_total);
    }
    
    if (frm.doc.total_qty !== combined_qty) {
        frappe.model.set_value(frm.doctype, frm.docname, 'total_qty', combined_qty);
    }

    // 2. Calculate Total with Delivery Fees
    let total_with_fee = combined_total + fee;
    
    if (frm.doc.total_with_delivery_fees !== total_with_fee) {
        frappe.model.set_value(frm.doctype, frm.docname, 'total_with_delivery_fees', total_with_fee);
    }
    
    // 3. Calculate Grand Total
    let discount = frm.doc.discount_amount || 0;
    if (frm.doc.additional_discount_percentage && !frm.doc.discount_amount) {
        discount = (total_with_fee * frm.doc.additional_discount_percentage) / 100;
    }
    
    let grand_total = total_with_fee - discount;
    if (frm.doc.grand_total !== grand_total) {
        frappe.model.set_value(frm.doctype, frm.docname, 'grand_total', grand_total);
    }
}

function render_custom_gallery(frm) {
    // We want to insert the gallery right before the items section.
    // If the section doesn't exist, we fall back to general wrapper logic.
    let $wrapper = frm.fields_dict.items ? $(frm.fields_dict.items.wrapper).closest('.section-body') : null;
    if (!$wrapper || $wrapper.length === 0) {
        $wrapper = $(frm.fields_dict.items.wrapper);
    }
    
    let $gallery = $wrapper.parent().find('.custom-gallery-container');
    
    if (!$gallery.length) {
        $gallery = $(`
            <div class="custom-gallery-container">
                <div class="custom-gallery-header">
                    <h4>Image Gallery</h4>
                    <div class="custom-gallery-actions">
                        <button class="btn btn-xs btn-default btn-bulk-download hidden" title="Download Selected">
                            <i class="fa fa-download"></i> <span class="hidden-xs">Download</span>
                        </button>
                        <button class="btn btn-xs btn-danger btn-bulk-delete hidden" title="Delete Selected">
                            <i class="fa fa-trash"></i> <span class="hidden-xs">Delete</span>
                        </button>
                        <button class="btn btn-xs btn-default btn-select-all" title="Select All">
                            <i class="fa fa-check-square-o"></i> <span class="hidden-xs">Select All</span>
                        </button>
                        <button class="btn btn-xs btn-primary btn-upload" title="Upload Image">
                            <i class="fa fa-upload"></i> <span class="hidden-xs">Upload</span>
                        </button>
                    </div>
                </div>
                <div class="custom-gallery-scroll"></div>
            </div>
        `);
        $gallery.insertBefore($wrapper);
        
        // Event listeners
        $gallery.find('.btn-upload').on('click', () => {
            new frappe.ui.FileUploader({
                doctype: frm.doc.doctype,
                docname: frm.doc.name,
                make_attachments_public: true,
                on_success: (file) => {
                    frm.reload_doc();
                }
            });
        });

        // Bulk Actions
        $gallery.find('.btn-bulk-delete').on('click', () => bulk_action(frm, $gallery, 'delete'));
        $gallery.find('.btn-bulk-download').on('click', () => bulk_action(frm, $gallery, 'download'));

        $gallery.find('.btn-select-all').on('click', () => {
            let items = $gallery.find('.custom-gallery-item');
            let allSelected = items.length > 0 && items.length === items.filter('.selected').length;
            if (allSelected) {
                items.removeClass('selected');
                items.find('.custom-gallery-item-selector i').removeClass('fa-check-square').addClass('fa-square-o');
            } else {
                items.addClass('selected');
                items.find('.custom-gallery-item-selector i').removeClass('fa-square-o').addClass('fa-check-square');
            }
            let checked = $gallery.find('.custom-gallery-item.selected').length;
            $gallery.find('.btn-bulk-delete, .btn-bulk-download').toggleClass('hidden', checked === 0);
        });

        // Drag and drop events
        $gallery.on('dragenter dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
            $gallery.addClass('dragover');
        });
        
        $gallery.on('dragleave drop', function(e) {
            e.preventDefault();
            e.stopPropagation();
            $gallery.removeClass('dragover');
        });

        $gallery.on('drop', function(e) {
            let files = e.originalEvent.dataTransfer.files;
            if (files && files.length > 0) {
                new frappe.ui.FileUploader({
                    doctype: frm.doc.doctype,
                    docname: frm.doc.name,
                    files: files,
                    make_attachments_public: true,
                    on_success: (file) => {
                        frm.reload_doc();
                    }
                });
            }
        });
    }

    // Fetch and render items
    frappe.db.get_list('File', {
        filters: {
            attached_to_doctype: frm.doc.doctype,
            attached_to_name: frm.doc.name,
            is_folder: 0
        },
        fields: ['name', 'file_name', 'file_url', 'is_private'],
        limit: 200
    }).then(files => {
        let images = files.filter(f => f.file_name && f.file_name.match(/\.(jpg|jpeg|png|gif|svg|webp)$/i));
        let $scroll = $gallery.find('.custom-gallery-scroll');
        $scroll.empty();

        if (images.length === 0) {
            $scroll.append('<p class="text-muted" style="padding-left: 15px; margin: 0;">No images uploaded yet.</p>');
            $gallery.find('.btn-bulk-download, .btn-bulk-delete').addClass('hidden');
            return;
        }

        images.forEach((img, idx) => {
            let $item = $(`
                <div class="custom-gallery-item" data-name="${img.name}" data-url="${img.file_url}" data-idx="${idx}">
                    <div class="custom-gallery-item-selector" title="Select"><i class="fa fa-square-o"></i></div>
                    <img src="${img.file_url}" />
                    <div class="custom-gallery-item-overlay">
                        <button class="btn btn-xs btn-default btn-gallery-download" title="Download"><i class="fa fa-download"></i></button>
                        <button class="btn btn-xs btn-danger btn-gallery-delete" title="Delete"><i class="fa fa-trash"></i></button>
                    </div>
                </div>
            `);
            $scroll.append($item);
        });

        bind_gallery_item_events(frm, $gallery, images);
    });
}

function bind_gallery_item_events(frm, $gallery, images) {
    let update_bulk_actions = () => {
        let checked = $gallery.find('.custom-gallery-item.selected').length;
        $gallery.find('.btn-bulk-delete, .btn-bulk-download').toggleClass('hidden', checked === 0);
    };

    $gallery.find('.custom-gallery-item-selector').on('click', function(e) {
        e.stopPropagation();
        let $item = $(this).closest('.custom-gallery-item');
        $item.toggleClass('selected');
        let $icon = $(this).find('i');
        if ($item.hasClass('selected')) {
            $icon.removeClass('fa-square-o').addClass('fa-check-square');
        } else {
            $icon.removeClass('fa-check-square').addClass('fa-square-o');
        }
        update_bulk_actions();
    });

    $gallery.find('.btn-gallery-delete').on('click', function(e) {
        e.stopPropagation();
        let name = $(this).closest('.custom-gallery-item').data('name');
        frappe.confirm('Are you sure you want to delete this image?', () => {
            frappe.call({
                method: 'frappe.client.delete',
                args: { doctype: 'File', name: name },
                callback: function(r) {
                    if (!r.exc) frm.reload_doc();
                }
            });
        });
    });

    $gallery.find('.btn-gallery-download').on('click', function(e) {
        e.stopPropagation();
        let name = $(this).closest('.custom-gallery-item').data('name');
        let url = $(this).closest('.custom-gallery-item').data('url');
        
        let link = document.createElement('a');
        link.href = url;
        link.download = name;
        link.target = '_blank';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });

    $gallery.find('.custom-gallery-item img').on('click', function(e) {
        let idx = $(this).closest('.custom-gallery-item').data('idx');
        open_previewer(images, idx);
    });
}

function bulk_action(frm, $gallery, action) {
    let selected = [];
    $gallery.find('.custom-gallery-item.selected').each(function() {
        let $item = $(this);
        selected.push({
            name: $item.data('name'),
            url: $item.data('url')
        });
    });

    if (action === 'delete') {
        frappe.confirm(`Are you sure you want to delete ${selected.length} image(s)?`, () => {
            let promises = selected.map(item => new Promise(resolve => {
                frappe.call({
                    method: 'frappe.client.delete',
                    args: { doctype: 'File', name: item.name },
                    callback: resolve
                });
            }));
            Promise.all(promises).then(() => frm.reload_doc());
        });
    } else if (action === 'download') {
        selected.forEach((item, i) => {
            setTimeout(() => {
                let link = document.createElement('a');
                link.href = item.url;
                link.download = item.name;
                link.target = '_blank';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }, i * 300);
        });
    }
}

function open_previewer(images, current_idx) {
    if ($('#custom-gallery-previewer').length) {
        $('#custom-gallery-previewer').remove();
    }

    let $previewer = $(`
        <div id="custom-gallery-previewer">
            <button class="btn-close-preview" title="Close"><i class="fa fa-times"></i></button>
            <button class="btn-prev-preview" title="Previous"><i class="fa fa-chevron-left"></i></button>
            <img class="preview-image" src="${images[current_idx].file_url}" />
            <button class="btn-next-preview" title="Next"><i class="fa fa-chevron-right"></i></button>
            <div class="preview-counter">${current_idx + 1} / ${images.length}</div>
        </div>
    `);

    $('body').append($previewer);

    let update_image = (idx) => {
        current_idx = (idx + images.length) % images.length;
        $previewer.find('.preview-image').attr('src', images[current_idx].file_url);
        $previewer.find('.preview-counter').text(`${current_idx + 1} / ${images.length}`);
    };

    $previewer.find('.btn-close-preview').on('click', () => $previewer.remove());
    $previewer.on('click', function(e) {
        if (e.target.id === 'custom-gallery-previewer') {
            $previewer.remove();
        }
    });
    $previewer.find('.btn-prev-preview').on('click', () => update_image(current_idx - 1));
    $previewer.find('.btn-next-preview').on('click', () => update_image(current_idx + 1));

    $(document).on('keydown.gallery', function(e) {
        if (!$('#custom-gallery-previewer').length) {
            $(document).off('keydown.gallery');
            return;
        }
        if (e.key === 'Escape') $previewer.remove();
        if (e.key === 'ArrowLeft') update_image(current_idx - 1);
        if (e.key === 'ArrowRight') update_image(current_idx + 1);
    });
}

// Auto-fill delivery_date and rate when a flower item is selected, and calculate amounts
frappe.ui.form.on('Flower Item', {
    flower_item: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.flower_item) {
            // Default delivery date to parent delivery date if not set
            frappe.model.set_value(cdt, cdn, 'delivery_date', frm.doc.delivery_date);

            // Fetch the rate from Item Price
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Item Price",
                    filters: {
                        item_code: row.flower_item,
                        price_list: frm.doc.selling_price_list || "Standard Selling",
                        selling: 1
                    },
                    fieldname: "price_list_rate"
                },
                callback: function(r) {
                    if (r.message && r.message.price_list_rate) {
                        frappe.model.set_value(cdt, cdn, 'rate', r.message.price_list_rate);
                        frappe.model.set_value(cdt, cdn, 'amount', r.message.price_list_rate * (row.qty || 1));
                        calculate_custom_totals(frm);
                    }
                }
            });
        }
    },
    qty: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, 'amount', (row.qty || 0) * (row.rate || 0));
        calculate_custom_totals(frm);
    },
    rate: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, 'amount', (row.qty || 0) * (row.rate || 0));
        calculate_custom_totals(frm);
    }
});

// When parent delivery date changes, update flower items just like standard items
frappe.ui.form.on('Sales Order', {
    delivery_date: function(frm) {
        // ERPNext handles standard items natively, we just need to update our custom flower items
        if (frm.doc.delivery_date && frm.doc.custom_flower_items && frm.doc.custom_flower_items.length > 0) {
            frappe.confirm('Do you want to update Delivery Date in all Flower Items?', () => {
                frm.doc.custom_flower_items.forEach(d => {
                    frappe.model.set_value(d.doctype, d.name, 'delivery_date', frm.doc.delivery_date);
                });
            });
        }
    }
});
