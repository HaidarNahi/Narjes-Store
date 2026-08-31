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

        render_customer_info(frm);

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
    customer: function(frm) {
        render_customer_info(frm);
    },
    governorate_of_delivery: function(frm) {
        setTimeout(() => calculate_custom_totals(frm), 500);
    },
    payment: function(frm) {
        // switching to/from Prepayment adds or removes the delivery fee
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

// Renders the read-only "Customer" tab: every field of the linked Customer,
// grouped the way the Customer form groups them. Values come from the live
// record (api.get_customer_info) rather than from mirrored fields on the Sales
// Order, so the tab is never a stale copy of the customer master.
// Read-only receipt: the order's own money and lines, shown above the customer
// record on the Receipt Info tab.
//
// Built from frm.doc rather than fetched: grand_total, items and
// custom_flower_items are already loaded on the form, so this cannot go stale
// against what the user is looking at, needs no endpoint, and no permission
// check of its own. It is re-rendered on every refresh (unlike the customer
// block, which is cached per customer) so editing a line updates it at once.
function render_receipt_block(frm) {
    const esc = frappe.utils.escape_html;
    const money = (v) => format_currency(v || 0, frm.doc.currency);

    const rows = (list, code_field, name_field) => (list || []).map((r) => `
        <tr>
            <td class="narjes-receipt-item">${esc(r[code_field] || '')}${
                r[name_field] && r[name_field] !== r[code_field]
                    ? `<span class="narjes-receipt-sub">${esc(r[name_field])}</span>` : ''
            }</td>
            <td class="narjes-receipt-num">${format_number(r.qty || 0, null,
                Number.isInteger(Number(r.qty)) ? 0 : 2)}</td>
            <td class="narjes-receipt-num">${money(r.rate)}</td>
            <td class="narjes-receipt-num">${money(r.amount)}</td>
        </tr>`).join('');

    const table = (label, body, count) => !count ? '' : `
        <section class="narjes-receipt-group">
            <h5>${esc(label)} <span class="narjes-receipt-count">${count}</span></h5>
            <div class="narjes-receipt-scroll">
                <table class="narjes-receipt-table">
                    <thead><tr>
                        <th>${__('Item')}</th>
                        <th class="narjes-receipt-num">${__('Qty')}</th>
                        <th class="narjes-receipt-num">${__('Rate')}</th>
                        <th class="narjes-receipt-num">${__('Amount')}</th>
                    </tr></thead>
                    <tbody>${body}</tbody>
                </table>
            </div>
        </section>`;

    const items = frm.doc.items || [];
    const flowers = frm.doc.custom_flower_items || [];

    return `
        <div class="narjes-receipt">
            <div class="narjes-receipt-total">
                <span class="narjes-receipt-total-label">${__('Total with Delivery Fees')}</span>
                <span class="narjes-receipt-total-value">${money(frm.doc.total_with_delivery_fees)}</span>
                ${frm.doc.delivery_fees ? `<span class="narjes-receipt-total-note">${
                    __('includes {0} delivery', [money(frm.doc.delivery_fees)])
                }</span>` : ''}
            </div>
            ${table(__('Items'), rows(items, 'item_code', 'item_name'), items.length)}
            ${table(__('Flower Items'), rows(flowers, 'flower_item', 'flower_item'), flowers.length)}
            ${!items.length && !flowers.length
                ? `<div class="narjes-customer-empty">${__('No lines on this order yet.')}</div>` : ''}
        </div>`;
}

function render_customer_info(frm) {
    const field = frm.get_field('custom_customer_info_html');
    if (!field) return;   // custom field not synced on this site yet

    const empty = (msg) =>
        `<div class="narjes-customer-empty">${frappe.utils.escape_html(msg)}</div>`;

    // Two independent blocks in one HTML field: the receipt repaints every
    // time, the customer record is fetched once per customer.
    let $host = field.$wrapper.find('.narjes-receipt-host');
    if (!$host.length) {
        field.$wrapper.html(
            `<div class="narjes-receipt-host"></div><div class="narjes-customer-host"></div>`
        );
        $host = field.$wrapper.find('.narjes-receipt-host');
    }
    $host.html(render_receipt_block(frm));

    const $customer = field.$wrapper.find('.narjes-customer-host');

    if (!frm.doc.customer) {
        $customer.html(empty(__('Select a customer to see their details here.')));
        return;
    }

    // Avoid refetching the same customer on every refresh of the same form.
    if (field.$wrapper.data('narjes-loaded-for') === frm.doc.customer) return;
    field.$wrapper.data('narjes-loaded-for', frm.doc.customer);

    frappe.call({
        method: 'narjes_custom.api.get_customer_info',
        args: { customer: frm.doc.customer },
    }).then((r) => {
        const data = r && r.message;
        if (!data || !data.groups || !data.groups.length) {
            $customer.html(empty(__('No customer details to show.')));
            return;
        }

        const esc = frappe.utils.escape_html;
        const groups = data.groups.map((group) => {
            const rows = group.fields.map((f) => `
                <div class="narjes-customer-field">
                    <div class="narjes-customer-label">${esc(f.label)}</div>
                    <div class="narjes-customer-value">${f.value || '&mdash;'}</div>
                </div>`).join('');
            return `
                <section class="narjes-customer-group">
                    ${group.label ? `<h5>${esc(group.label)}</h5>` : ''}
                    <div class="narjes-customer-grid">${rows}</div>
                </section>`;
        }).join('');

        $customer.html(`
            <div class="narjes-customer-info">
                <div class="narjes-customer-head">
                    <span class="narjes-customer-name">${esc(data.customer_name || data.customer)}</span>
                    <a href="/app/customer/${encodeURIComponent(data.customer)}"
                       class="narjes-customer-open">${__('Open customer')} &rarr;</a>
                </div>
                ${groups}
            </div>`);
    }).catch(() => {
        field.$wrapper.data('narjes-loaded-for', null);
        $customer.html(empty(__('Could not load customer details.')));
    });
}

function update_weekday_label(frm, fieldname) {
    let $wrapper = frm.get_field(fieldname).$wrapper;
    if ($wrapper.find('.weekday-label').length === 0) {
        $wrapper.find('.control-input').after('<div class="weekday-label text-muted small" style="margin-top: 4px; font-weight: 600;"></div>');
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

// Writes a computed value ONLY when it genuinely differs from what's already
// on the doc.
//
// This guard is what stops the save→"Draft"→"Not Saved" flip that used to
// force a double-save before an order could be submitted. The old code
// compared with `!==` against raw field values, but an unset Currency/Float
// field arrives from the server as `null` (or `undefined` on a fresh doc),
// and `null !== 0` is true — so every post-save `refresh` re-set these fields
// to 0, marking the freshly-saved document dirty again ~500ms later. It only
// "worked" on the second save because by then the zeros were persisted.
// flt() normalises null/undefined/"" to 0, and rounding to the field's own
// precision also stops float dust (0.1+0.2) from re-dirtying the form.
// `frm.precision()` does not exist on frappe.ui.form.Form (v16) — calling it
// threw "frm.precision is not a function" and aborted calculate_custom_totals
// before it ever wrote a field, so the live preview silently stopped working.
// frappe.meta.get_field_precision is the supported lookup.
function set_if_changed(frm, fieldname, value) {
    const df = frappe.meta.get_docfield(frm.doctype, fieldname, frm.docname);
    const precision = (df ? frappe.meta.get_field_precision(df, frm.doc) : null) ?? 2;
    if (flt(frm.doc[fieldname], precision) !== flt(value, precision)) {
        frappe.model.set_value(frm.doctype, frm.docname, fieldname, value);
        return true;
    }
    return false;
}

function calculate_custom_totals(frm) {
    if (frm.doc.docstatus !== 0) return;

    // Never recalculate a document the user hasn't started editing.
    //
    // This is what fixes the save -> "Draft" -> "Not Saved" flip that forced a
    // double-save before an order could be submitted. These totals are also
    // computed server-side (api.sales_order_validate), and the two sides do
    // not always agree — e.g. an order with flower items persists
    // total=40,000 (items + flowers) alongside net_total=30,000 (items only),
    // so this function would compute grand_total=36,000, see the stored
    // 26,000, and write it. Running on `refresh` meant that happened ~500ms
    // after every save, marking the just-saved document dirty again; it also
    // meant a freshly opened order was already dirty before anyone touched it.
    //
    // While the user IS editing, the live preview still runs as before. The
    // server stays authoritative for what actually gets stored.
    if (!frm.is_new() && !frm.is_dirty()) return;

    // 1. Calculate Delivery Fees based on Governorate.
    // Read live from Narjes Settings (exposed via frappe.boot.narjes_settings
    // — see extend_bootinfo in api.py) instead of hardcoding 4000/6000 here,
    // so this client-side preview can never silently drift from what an
    // admin has configured (see NARJES_STORE_SYSTEM.md §14.5/§14.6).
    let fee = 0;
    // Prepaid orders go out by taxi and the customer pays the driver directly,
    // so the shop never handles a delivery fee — mirrors the same rule in
    // api.sales_order_before_validate so the form and the saved doc agree.
    if (frm.doc.governorate_of_delivery && frm.doc.payment !== 'Prepayment') {
        let ns = (frappe.boot && frappe.boot.narjes_settings) || {};
        if (frm.doc.governorate_of_delivery === 'بغداد') {
            fee = ns.baghdad_delivery_fee || 0;
        } else {
            fee = ns.other_governorate_delivery_fee || 0;
        }
    }
    
    set_if_changed(frm, 'delivery_fees', fee);

    // Calculate Flower Total and Qty
    let flower_total = 0;
    let flower_qty = 0;
    (frm.doc.custom_flower_items || []).forEach(row => {
        flower_total += (row.amount || 0);
        flower_qty += (row.qty || 0);
    });

    set_if_changed(frm, 'custom_flower_total', flower_total);

    // Refresh totals if needed
    frm.refresh_field('custom_flower_total');

    // Mutate Frappe standard total fields to include flowers (UI Only)
    let standard_total = frm.doc.items ? frm.doc.items.reduce((sum, row) => sum + (row.amount || 0), 0) : 0;
    let combined_total = standard_total + flower_total;
    
    let standard_qty = frm.doc.items ? frm.doc.items.reduce((sum, row) => sum + (row.qty || 0), 0) : 0;
    let combined_qty = standard_qty + flower_qty;

    if (set_if_changed(frm, 'total', combined_total)) {
        set_if_changed(frm, 'net_total', combined_total);
    }

    set_if_changed(frm, 'total_qty', combined_qty);

    // 2. Grand Total — WITHOUT the delivery fee.
    //
    // The courier collects the delivery portion and keeps it; it never reaches
    // the shop, so it is not part of what the shop charges and must not sit in
    // grand_total (which is what feeds the ledger). The discount likewise
    // applies to the shop's own goods, never to the courier's fee.
    let discount = frm.doc.discount_amount || 0;
    if (frm.doc.additional_discount_percentage && !frm.doc.discount_amount) {
        discount = (combined_total * frm.doc.additional_discount_percentage) / 100;
    }

    let grand_total = combined_total - discount;
    set_if_changed(frm, 'grand_total', grand_total);

    // 3. What the customer hands to the courier — the sticker figure.
    set_if_changed(frm, 'total_with_delivery_fees', grand_total + fee);
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
                            ${narjes_icon('download-simple', {size: 'xs'})} <span class="hidden-xs">Download</span>
                        </button>
                        <button class="btn btn-xs btn-danger btn-bulk-delete hidden" title="Delete Selected">
                            ${narjes_icon('trash', {size: 'xs'})} <span class="hidden-xs">Delete</span>
                        </button>
                        <button class="btn btn-xs btn-default btn-select-all" title="Select All">
                            ${narjes_icon('check-square', {size: 'xs'})} <span class="hidden-xs">Select All</span>
                        </button>
                        <button class="btn btn-xs btn-primary btn-upload" title="Upload Image">
                            ${narjes_icon('upload-simple', {size: 'xs'})} <span class="hidden-xs">Upload</span>
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
                items.find('.custom-gallery-item-selector use').attr('href', '#ph-square');
            } else {
                items.addClass('selected');
                items.find('.custom-gallery-item-selector use').attr('href', '#ph-check-square');
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
                <div class="custom-gallery-item" data-name="${img.name}" data-url="${img.file_url}" data-idx="${idx}" data-filename="${frappe.utils.escape_html(img.file_name || '')}">
                    <div class="custom-gallery-item-selector" title="Select">${narjes_icon('square', {size: 'lg'})}</div>
                    <img src="${img.file_url}" />
                    <div class="custom-gallery-item-overlay">
                        <button class="btn btn-xs btn-default btn-gallery-download" title="Download">${narjes_icon('download-simple', {size: 'xs'})}</button>
                        <button class="btn btn-xs btn-danger btn-gallery-delete" title="Delete">${narjes_icon('trash', {size: 'xs'})}</button>
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
        $(this).find('use').attr('href', $item.hasClass('selected') ? '#ph-check-square' : '#ph-square');
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
        const $item = $(this).closest('.custom-gallery-item');
        download_images([{
            url: $item.data('url'),
            // data('name') is the File DOCNAME — a random hash. Downloading
            // under it is what renamed every saved image to gibberish. The
            // real upload name is file_name, carried in data-filename.
            filename: $item.data('filename') || $item.data('name'),
        }]);
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
            url: $item.data('url'),
            filename: $item.data('filename') || $item.data('name'),
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
        download_images(selected);
    }
}

// ── Downloading ──────────────────────────────────────────────────────────
// Two things the old implementation got wrong:
//   * it saved under the File docname (a random hash) instead of the
//     uploaded file name;
//   * it fired the download straight into the browser's download folder with
//     no chance to choose where it lands.
//
// The File System Access API fixes the second: showSaveFilePicker for a
// single image, showDirectoryPicker for a batch, both of which open the real
// Finder/Explorer dialog. It needs a secure context and a user gesture — both
// true here — and is unsupported in Firefox and older Safari, so the classic
// anchor download stays as a fallback. That fallback now at least uses the
// correct name.
function _anchor_download(items) {
    items.forEach((item, i) => {
        setTimeout(() => {
            const link = document.createElement('a');
            link.href = item.url;
            link.download = item.filename || item.name;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }, i * 300);
    });
}

async function _fetch_blob(url) {
    // same-origin, cookies included so /private/files works
    const res = await fetch(url, { credentials: 'same-origin' });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return await res.blob();
}

async function download_images(items) {
    if (!items || !items.length) return;

    const single = items.length === 1;
    const can_pick = single ? !!window.showSaveFilePicker : !!window.showDirectoryPicker;

    if (!can_pick) {
        _anchor_download(items);
        return;
    }

    try {
        if (single) {
            const name = items[0].filename || items[0].name;
            const ext = (name.split('.').pop() || '').toLowerCase();
            const handle = await window.showSaveFilePicker({
                suggestedName: name,
                types: ext ? [{
                    description: __('Image'),
                    accept: { [`image/${ext === 'jpg' ? 'jpeg' : ext}`]: [`.${ext}`] },
                }] : undefined,
            });
            const blob = await _fetch_blob(items[0].url);
            const writable = await handle.createWritable();
            await writable.write(blob);
            await writable.close();
            frappe.show_alert({ message: __('Saved {0}', [name]), indicator: 'green' });
            return;
        }

        const dir = await window.showDirectoryPicker({ mode: 'readwrite' });
        let saved = 0;
        const failed = [];
        for (const item of items) {
            const name = item.filename || item.name;
            try {
                const blob = await _fetch_blob(item.url);
                const handle = await dir.getFileHandle(name, { create: true });
                const writable = await handle.createWritable();
                await writable.write(blob);
                await writable.close();
                saved++;
            } catch (err) {
                failed.push(name);
            }
        }
        if (saved) {
            frappe.show_alert({
                message: __('Saved {0} image(s)', [saved]), indicator: 'green',
            });
        }
        if (failed.length) {
            frappe.msgprint({
                title: __('Some images could not be saved'),
                message: failed.map(frappe.utils.escape_html).join('<br>'),
                indicator: 'orange',
            });
        }
    } catch (err) {
        // The user dismissing the picker is a normal outcome, not a failure.
        if (err && (err.name === 'AbortError' || err.name === 'NotAllowedError')) return;
        frappe.show_alert({
            message: __('Could not save — falling back to your downloads folder.'),
            indicator: 'orange',
        });
        _anchor_download(items);
    }
}

function open_previewer(images, current_idx) {
    if ($('#custom-gallery-previewer').length) {
        $('#custom-gallery-previewer').remove();
    }

    let $previewer = $(`
        <div id="custom-gallery-previewer">
            <button class="btn-close-preview" title="Close">${narjes_icon('x', {size: 'md'})}</button>
            <button class="btn-prev-preview" title="Previous">${narjes_icon('caret-left', {size: 'lg'})}</button>
            <img class="preview-image" src="${images[current_idx].file_url}" />
            <button class="btn-next-preview" title="Next">${narjes_icon('caret-right', {size: 'lg'})}</button>
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
