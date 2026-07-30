// ============================================================
// sales_order_list.js — Narjes Custom Kanban for Sales Orders
// ============================================================

// SECTION 1: Drag-and-Drop Business Rules
// --------------------------------------------------------
// Intercept frappe.call globally to enforce rules when cards
// are dragged between Kanban columns on the "Order Phases" board.
if (!frappe._narjes_call_patched) {
    frappe._narjes_call_patched = true;
    const _original_call = frappe.call;

    frappe.call = function (...args) {
        const options = args[0];
        if (
            options &&
            typeof options === "object" &&
            options.method === "frappe.desk.doctype.kanban_board.kanban_board.update_order_for_single_card" &&
            options.args &&
            options.args.board_name === "Order Phases"
        ) {
            const docname = options.args.docname;
            const new_status = options.args.to_colname;
            const deferred = $.Deferred();

            frappe.db.get_value("Sales Order", docname, "docstatus").then((db_r) => {
                const docstatus = db_r.message ? db_r.message.docstatus : 0;

                // RULE 1: Cancelled orders can NEVER be moved
                if (docstatus === 2) {
                    frappe.dom && frappe.dom.unfreeze && frappe.dom.unfreeze();
                    frappe.msgprint({ title: __("Not Allowed"), message: __("Cancelled orders cannot be moved."), indicator: "red" });
                    setTimeout(() => location.reload(), 1500);
                    deferred.reject();
                    return;
                }

                // RULE 2: Submitted orders can ONLY move to Cancelled
                if (docstatus === 1 && new_status !== "Cancelled") {
                    frappe.dom && frappe.dom.unfreeze && frappe.dom.unfreeze();
                    frappe.msgprint({ title: __("Not Allowed"), message: __("You cannot move a Submitted order back to a Draft phase."), indicator: "red" });
                    setTimeout(() => location.reload(), 1500);
                    deferred.reject();
                    return;
                }

                // RULE 3: Moving to "Done" → confirm and submit
                if (new_status === "Done") {
                    frappe.dom && frappe.dom.unfreeze && frappe.dom.unfreeze();
                    frappe.confirm("Are you sure you want to Submit this order? This action cannot be undone.", () => {
                        frappe.dom && frappe.dom.freeze && frappe.dom.freeze();
                        const orig_cb = options.callback;
                        options.callback = function (r) {
                            if (orig_cb) orig_cb(r);
                            if (r.exc) return;
                            frappe.db.get_doc("Sales Order", docname).then((doc) => {
                                frappe.call({
                                    method: "frappe.client.submit", args: { doc }, callback: (sr) => {
                                        if (!sr.exc) frappe.show_alert({ message: "Order Submitted Successfully", indicator: "green" });
                                        else location.reload();
                                    }
                                });
                            });
                        };
                        const req = _original_call.apply(frappe, args);
                        if (req && req.then) req.then(deferred.resolve).fail(deferred.reject);
                        else deferred.resolve();
                    }, () => { location.reload(); deferred.reject(); });

                    // RULE 4: Moving to "Cancelled" → confirm and cancel
                } else if (new_status === "Cancelled") {
                    frappe.dom && frappe.dom.unfreeze && frappe.dom.unfreeze();
                    frappe.confirm("Are you sure you want to Cancel this order?", () => {
                        frappe.dom && frappe.dom.freeze && frappe.dom.freeze();
                        const orig_cb = options.callback;
                        options.callback = function (r) {
                            if (orig_cb) orig_cb(r);
                            if (r.exc) return;
                            if (docstatus === 0) {
                                frappe.call({
                                    method: "narjes_custom.api.discard_draft", args: { docname }, callback: (cr) => {
                                        frappe.show_alert({ message: "Draft Order Discarded", indicator: "red" });
                                        location.reload();
                                    }
                                });
                            } else {
                                frappe.call({
                                    method: "narjes_custom.api.cancel_sales_order_and_links", args: { docname }, callback: (cr) => {
                                        if (!cr.exc) frappe.show_alert({ message: "Order & Linked Documents Cancelled", indicator: "red" });
                                        else location.reload();
                                    }
                                });
                            }
                        };
                        const req = _original_call.apply(frappe, args);
                        if (req && req.then) req.then(deferred.resolve).fail(deferred.reject);
                        else deferred.resolve();
                    }, () => { location.reload(); deferred.reject(); });

                    // RULE 5: Normal draft-to-draft move
                } else {
                    const req = _original_call.apply(frappe, args);
                    if (req && req.then) req.then(deferred.resolve).fail(deferred.reject);
                    else deferred.resolve();
                }
            });

            return deferred.promise();
        }

        return _original_call.apply(frappe, args);
    };
}

// SECTION 2: Custom Kanban Card Renderer
// --------------------------------------------------------
// The KanbanBoardCard function is called for EVERY card:
//   frappe.views.KanbanBoardCard(card, wrapper)
// where `card` is the object from prepare_card() containing:
//   card.name, card.title, card.creation, card._liked_by,
//   card.doc (the raw fetched fields), card.doctype, etc.

function narjes_custom_card(card, wrapper) {
    if (!card) return;

    const doc = card.doc || card; // raw field data

    // --- Data extraction ---
    const customer = doc.customer || card.title || "No Customer";
    const username = doc.username || "No Username";
    const delivery_id = doc.delivery_id || "No Delivery ID";

    // Delivery day: weekday name + date
    let delivery_day = "";
    if (doc.delivery_date) {
        const d = new Date(doc.delivery_date);
        const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
        delivery_day = days[d.getDay()] + " " + frappe.datetime.obj_to_user(doc.delivery_date);
    }

    // Time ago (relative creation time)
    let time_ago = "";
    if (card.creation) {
        time_ago = frappe.datetime.comment_when(card.creation) || "";
        // Strip wrapping quotes if present
        if (time_ago.startsWith('"') && time_ago.endsWith('"')) {
            time_ago = time_ago.slice(1, -1);
        }
    }

    // Priority flag: FILLED glyph when a priority is set, outline when not.
    // Grades ride the Narjes ramps — High = stamp (danger), Medium = saffron
    // (the accent proper, not its darker text tone — this is an icon fill),
    // Low = a calm fern-400 (the palette has no blue; fern carries "info").
    const priority = doc.priority || "";
    let flag_color = "currentColor";
    if (priority === "High") flag_color = NARJES_BRAND.danger;
    else if (priority === "Medium") flag_color = NARJES_BRAND.saffron;
    else if (priority === "Low") flag_color = NARJES_BRAND.fernSoft;

    // Conditional icons
    const has_flower = doc.has_flower ? true : false;
    const has_stand = doc.has_stand ? true : false;
    const has_gift = doc.gift ? true : false;

    // Liked?
    let is_liked = false;
    try {
        const liked_by = JSON.parse(card._liked_by || "[]");
        is_liked = liked_by.includes(frappe.session.user);
    } catch (e) { }

    // Owner
    const owner_raw = doc.owner || card.owner || "Unknown";
    const owner_display = owner_raw.split("@")[0];

    // --- Phosphor Icons (narjes_icon(), from the app's own sprite) ---
    // flag/heart use an explicit color style since they carry state-dependent
    // color (priority / liked) rather than just inheriting currentColor.
    const flag_svg = narjes_icon(priority ? 'flag-fill' : 'flag', {size: 'md', class: 'so-flag'}).replace('<svg ', `<svg style="color:${flag_color}" `);
    const flower_svg = narjes_icon('flower', {size: 'md'});
    const stand_svg = narjes_icon('potted-plant', {size: 'md'});
    const gift_svg = narjes_icon('gift', {size: 'md'});
    // Solid heart glyph when liked, outline glyph otherwise — matching
    // Phosphor's own regular/fill weight pair instead of faking a fill
    // toggle on a single stroke-based icon.
    const heart_color = is_liked ? NARJES_BRAND.danger : 'currentColor';
    const heart_svg = narjes_icon(is_liked ? 'heart-fill' : 'heart', {size: 'md', class: `so-heart ${is_liked ? 'liked' : ''}`}).replace('<svg ', `<svg style="color:${heart_color}" `);

    // Build right-side icons (always flag first, then conditionally flower/stand/gift)
    let icons_html = `<div class="so-icon" title="Priority: ${priority || 'None'}">${flag_svg}</div>`;
    if (has_flower) icons_html += `<div class="so-icon" title="Contains Flower">${flower_svg}</div>`;
    if (has_stand) icons_html += `<div class="so-icon" title="Contains Stand">${stand_svg}</div>`;
    if (has_gift) icons_html += `<div class="so-icon" title="Gift">${gift_svg}</div>`;

    // --- Full Card HTML ---
    const html = `
        <div class="kanban-card-wrapper" data-name="${card.name}">
            <div class="so-kanban-card">
                <div class="so-content-row">
                    <div class="so-left">
                        <div class="so-title-row"><a href="/app/sales-order/${card.name}">${customer}</a></div>
                        <div class="so-info-row">${username}</div>
                        <div class="so-info-row">${delivery_id}</div>
                        <div class="so-info-row">${delivery_day}</div>
                        <div class="so-info-row so-time-ago">${time_ago}</div>
                    </div>
                    <div class="so-divider"></div>
                    <div class="so-right">
                        ${icons_html}
                    </div>
                </div>
                <div class="so-heart-btn" data-name="${card.name}">${heart_svg}</div>
                <div class="so-creator-badge" title="Created By: ${owner_raw}">${owner_display}</div>
            </div>
        </div>
    `;

    const $card = $(html).appendTo(wrapper);

    // --- Favorite (Like) toggle ---
    $card.find(".so-heart-btn").on("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const $heart_btn = $(this);
        const currently_liked = $card.find(".so-heart").hasClass("liked");
        const add = currently_liked ? "No" : "Yes";

        frappe.call({
            method: "frappe.desk.like.toggle_like",
            quiet: true,
            args: { doctype: "Sales Order", name: card.name, add: add },
            callback: function (r) {
                if (r.exc) return;
                const now_liked = add === "Yes";
                const color = now_liked ? NARJES_BRAND.danger : "currentColor";
                $heart_btn.html(
                    narjes_icon(now_liked ? "heart-fill" : "heart", {size: "md", class: `so-heart ${now_liked ? "liked" : ""}`})
                        .replace("<svg ", `<svg style="color:${color}" `)
                );
            },
        });
    });

    // Undraggable without write access
    if (!frappe.model.can_write("Sales Order")) {
        $card.find(".so-kanban-card").css("cursor", "default");
    }

    return { $card };
}

// SECTION 3: Intercept KanbanBoardCard Assignment
// --------------------------------------------------------
// The kanban_board.bundle.js loads LAZILY (as required_libs).
// It assigns frappe.views.KanbanBoardCard AFTER our script runs.
// We use Object.defineProperty to intercept the setter so that
// the moment the bundle sets it, we replace it with our custom
// card — but ONLY for Sales Order. Other doctypes get the original.

if (!frappe._narjes_kanban_intercepted) {
    frappe._narjes_kanban_intercepted = true;

    let _original_KanbanBoardCard = frappe.views.KanbanBoardCard; // might be undefined initially

    Object.defineProperty(frappe.views, "KanbanBoardCard", {
        get: function () {
            // Return a wrapper that routes Sales Order cards to our custom renderer
            return function (card, wrapper) {
                if (card && card.doctype === "Sales Order") {
                    return narjes_custom_card(card, wrapper);
                }
                // For all other doctypes, use the original Frappe card
                if (_original_KanbanBoardCard) {
                    return _original_KanbanBoardCard(card, wrapper);
                }
            };
        },
        set: function (val) {
            // Capture the original when the bundle loads
            _original_KanbanBoardCard = val;
        },
        configurable: true,
        enumerable: true,
    });
}

// SECTION 4: Force Backend to Fetch Custom Fields
// --------------------------------------------------------
// Frappe's KanbanView.set_fields() reads board.fields to decide
// which columns to SELECT from the database. We patch get_fields()
// to guarantee our custom fields are always included for Sales Order.

frappe.router.on("change", () => {
    if (frappe.views && frappe.views.KanbanView && !frappe.views.KanbanView._narjes_fields_patched) {
        frappe.views.KanbanView._narjes_fields_patched = true;
        const orig_set_fields = frappe.views.KanbanView.prototype.set_fields;
        frappe.views.KanbanView.prototype.set_fields = function () {
            orig_set_fields.apply(this);
            if (this.doctype === "Sales Order") {
                const needed = ["customer", "username", "delivery_id", "delivery_date", "gift", "has_flower", "has_stand", "priority", "owner"];
                needed.forEach((f) => {
                    this._add_field(f);
                });
            }
        };
    }
});

// SECTION 5: ListView Settings (redirect to Kanban)
// --------------------------------------------------------
frappe.listview_settings["Sales Order"] = {
    onload: function (listview) {
        if (frappe.get_route()[2] !== "Kanban") {
            frappe.set_route("List", "Sales Order", "Kanban", "Order Phases");
        }
    },
};
