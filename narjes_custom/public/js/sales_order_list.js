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

                // RULE 3: Moving to "Done" → confirm, submit, and only then move
                //
                // Submit FIRST, move the card second. The original order was the
                // other way round: update_order_for_single_card ran first (which
                // writes order_phase = "Done"), and the submit went in its
                // callback. When the submit failed — short stock, a validation
                // error, anything — the phase change had already been committed,
                // so the ticket sat in Done as a Draft. The board then said the
                // order was finished while ERPNext said it had never been
                // submitted, and no amount of retrying reconciled the two.
                //
                // Submitting first means a failure leaves the order exactly where
                // it was, and the card snaps back on reload.
                if (new_status === "Done") {
                    frappe.dom && frappe.dom.unfreeze && frappe.dom.unfreeze();
                    frappe.confirm("Are you sure you want to Submit this order? This action cannot be undone.", () => {
                        frappe.dom && frappe.dom.freeze && frappe.dom.freeze();
                        frappe.call({
                            method: "narjes_custom.api.submit_and_mark_done",
                            args: { docname },
                            callback: (sr) => {
                                frappe.dom && frappe.dom.unfreeze && frappe.dom.unfreeze();
                                if (sr.exc) {
                                    // The server rolled the whole thing back, so the
                                    // order is still a draft in its old phase. Reload
                                    // to put the card back where it belongs; the error
                                    // dialog frappe already raised stays on screen.
                                    deferred.reject();
                                    setTimeout(() => location.reload(), 2500);
                                    return;
                                }
                                frappe.show_alert({ message: "Order Submitted Successfully", indicator: "green" });
                                deferred.resolve();
                                location.reload();
                            },
                            error: () => {
                                frappe.dom && frappe.dom.unfreeze && frappe.dom.unfreeze();
                                deferred.reject();
                                setTimeout(() => location.reload(), 2500);
                            }
                        });
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

// SECTION 2: Touch Scrolling on iPad
// --------------------------------------------------------
// Two separate faults made the columns unscrollable on a tablet:
//
//   a) The column body was not a real scroll container in our theme, so a
//      touch that ran past the end of the list was handed to the page and
//      rubber-banded the whole board. Fixed in CSS — .kanban-cards now owns
//      `overscroll-behavior: contain` and `touch-action: pan-y`.
//
//   b) Frappe builds the card sortable with no `delay`
//      (kanban_board.bundle.js → KanbanBoardColumn.setup_sortable), and
//      SortableJS with delay 0 claims the very first touchmove. Every swipe
//      that began on a card was therefore a drag, which is why the only
//      place that scrolled was the empty gap between tickets.
//
// (b) is fixed here. Frappe is a vendored app we do not patch, so we wrap
// the global Sortable.create instead — and only that, because the CARD
// sortable is the one built with Sortable.create(). The column-reorder
// sortable and the grid-row sortables use `new Sortable(...)` and are left
// completely alone.
//
// delayOnTouchOnly keeps the mouse behaviour identical: pointer drags still
// start instantly, only touch has to press-and-hold.
if (!frappe._narjes_sortable_patched && window.Sortable && Sortable.create) {
    frappe._narjes_sortable_patched = true;
    const _original_create = Sortable.create.bind(Sortable);

    Sortable.create = function (el, options) {
        if (el && el.classList && el.classList.contains("kanban-cards")) {
            options = Object.assign({}, options, {
                delay: 180,              // press-and-hold before a card lifts
                delayOnTouchOnly: true,  // ...on touch only; mouse is unchanged
                touchStartThreshold: 5,  // ignore finger jitter while holding
                fallbackTolerance: 5,
                scroll: true,
                scrollSensitivity: 60,
                forceAutoScrollFallback: true,
            });
        }
        return _original_create(el, options);
    };
}

// SECTION 3: Helpers
// --------------------------------------------------------

// Full name for a user, not the email local-part (issue #2).
//
// frappe.user_info() falls back to returning the raw uid as `fullname` when
// the user is missing from boot.user_info, which on a busy board shows an
// email again. So we resolve misses once, in one round trip, and push them
// into the boot cache via frappe.update_user_info() — after which every
// later card render is synchronous.
const NARJES_PENDING_USERS = new Set();
const NARJES_UNRESOLVED = new Set(); // asked for, came back empty — stop retrying
let NARJES_USER_TIMER = null;

function narjes_full_name(uid) {
    if (!uid) return "";
    const info = frappe.boot.user_info && frappe.boot.user_info[uid];
    if (info && info.fullname && info.fullname !== uid) return info.fullname;

    // Not resolvable yet — queue it and show something sane meanwhile.
    if (uid.includes("@") && !NARJES_UNRESOLVED.has(uid)) {
        NARJES_PENDING_USERS.add(uid);
        narjes_schedule_user_fetch();
    }
    return info && info.fullname ? info.fullname : uid;
}

// A board paints all its cards in one synchronous pass, so a zero-delay
// timeout batches every miss on the board into a single round trip.
function narjes_schedule_user_fetch() {
    if (NARJES_USER_TIMER) return;
    NARJES_USER_TIMER = setTimeout(() => {
        NARJES_USER_TIMER = null;
        const uids = Array.from(NARJES_PENDING_USERS);
        NARJES_PENDING_USERS.clear();
        if (!uids.length) return;

        frappe.db
            .get_list("User", {
                filters: [["name", "in", uids]],
                fields: ["name", "full_name", "user_image"],
                limit: uids.length,
            })
            .then((rows) => {
                const patch = {};
                (rows || []).forEach((r) => {
                    patch[r.name] = {
                        fullname: r.full_name || r.name,
                        image: r.user_image,
                        name: r.name,
                    };
                });
                // Anything the query did not return is unreadable to us
                // (deleted, or no permission) — remember so we don't ask again
                // on every repaint.
                uids.forEach((u) => {
                    if (!patch[u]) NARJES_UNRESOLVED.add(u);
                });
                if (!Object.keys(patch).length) return;

                frappe.update_user_info(patch);
                // Repaint the stamps/chips that were showing a fallback.
                $(".so-kanban-card").each(function () {
                    const $c = $(this);
                    const owner = $c.attr("data-owner");
                    if (patch[owner]) {
                        $c.find(".so-creator-badge")
                            .text(patch[owner].fullname)
                            .attr("title", __("Created by") + ": " + patch[owner].fullname);
                    }
                    const asg = $c.attr("data-assignee");
                    if (asg && patch[asg]) {
                        const full = patch[asg].fullname;
                        $c.find(".so-assignee .so-assignee-name").text(full.split(" ")[0]);
                        // initials were derived from the email until now
                        $c.find(".so-assignee .so-avatar")
                            .not(".so-avatar-empty")
                            .text(narjes_initials(full));
                    }
                });
            });
    }, 0);
}

// Avatar tint. Frappe's own get_palette() returns its stock blue/pink/orange
// ramp, which has no place on a Narjes board — these are brand tones, all
// dark enough to carry white initials at AA.
const NARJES_AVATAR_TONES = [
    "var(--n-fern-600)",
    "var(--n-fern-700)",
    "var(--n-fern-500)",
    "var(--n-saffron-700)",
    "var(--n-stamp-500)",
    "var(--n-neutral-700)",
];

function narjes_avatar_tone(seed) {
    let h = 0;
    const s = String(seed || "");
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return NARJES_AVATAR_TONES[h % NARJES_AVATAR_TONES.length];
}

function narjes_initials(name) {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "?";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function narjes_escape(value) {
    return frappe.utils.escape_html(String(value == null ? "" : value));
}

// SECTION 4: Custom Kanban Card Renderer
// --------------------------------------------------------
// Called for EVERY card as frappe.views.KanbanBoardCard(card, wrapper).
// `card` comes from prepare_card(): card.name, card.title, card.creation,
// card.assigned_list, card.doc (raw fetched fields), card.doctype.

function narjes_custom_card(card, wrapper) {
    if (!card) return;

    const doc = card.doc || card; // raw field data

    // --- Data extraction ---
    // Placeholder strings are gone (issue #11): a row is emitted only when
    // its field actually has a value, so the card shrinks instead of showing
    // "No Username" / "No Delivery ID".
    const customer = doc.customer || card.title || __("No Customer");
    const username = doc.username || "";
    const delivery_id = doc.delivery_id || "";

    // Delivery day: weekday name + date
    let delivery_day = "";
    if (doc.delivery_date) {
        const d = new Date(doc.delivery_date);
        const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
        delivery_day = days[d.getDay()] + " " + frappe.datetime.obj_to_user(doc.delivery_date);
    }

    // Time ago. prepare_card() rewrites card.creation to "MMM DD, YYYY",
    // which loses the clock — doc.creation is still the raw timestamp, so
    // prefer it and keep card.creation only as a fallback.
    //
    // prettyDate(), NOT comment_when(): comment_when returns a whole
    // `<span class="frappe-timestamp" ...>` element, and running that through
    // the HTML escaper printed the markup on the card as literal text.
    // prettyDate gives the bare "21 hours ago" string.
    //
    // We still put frappe-timestamp + data-timestamp on our own row, because
    // frappe.datetime.refresh_when() walks .frappe-timestamp and rewrites the
    // contents — so the label keeps ageing on its own without a board reload.
    let time_ago = "";
    const raw_creation = doc.creation || card.creation;
    if (raw_creation) {
        time_ago = frappe.datetime.prettyDate(raw_creation) || "";
    }

    // Grand total (issue #4), labelled in the order's own currency.
    // Whole amounts print without decimals — IQD has no minor unit and
    // ".00" on every card is just noise — but a currency that actually
    // carries fractions still shows them.
    let total_html = "";
    if (doc.grand_total != null && doc.grand_total !== "") {
        const value = Number(doc.grand_total);
        const currency = doc.currency || frappe.defaults.get_default("currency") || "";
        const amount = format_number(value, null, Number.isInteger(value) ? 0 : 2);
        total_html =
            `<span class="so-total-value">${narjes_escape(amount)}` +
            (currency ? `<span class="so-total-currency">${narjes_escape(currency)}</span>` : "") +
            `</span>`;
    }

    // Priority flag: FILLED glyph when a priority is set, outline when not.
    // Grades ride the Narjes ramps — High = stamp (danger), Medium = saffron,
    // Low = a calm fern-400 (the palette has no blue; fern carries "info").
    const priority = doc.priority || "";
    let priority_class = "";
    if (priority === "High") priority_class = "pri-high";
    else if (priority === "Medium") priority_class = "pri-medium";
    else if (priority === "Low") priority_class = "pri-low";

    // Conditional markers
    const has_flower = !!doc.has_flower;
    const has_stand = !!doc.has_stand;
    const has_gift = !!doc.gift;

    // Owner → full name (issue #2)
    const owner_raw = doc.owner || card.owner || "";
    const owner_display = narjes_full_name(owner_raw) || __("Unknown");

    // Assignee (issue #5). _assign is already fetched by Frappe's kanban
    // view, and prepare_card() parses it into assigned_list — no extra field
    // needed. We surface the first assignee; the picker manages the rest.
    const assigned = card.assigned_list || [];
    const assignee = assigned.length ? assigned[0] : "";
    const assignee_name = assignee ? narjes_full_name(assignee) : "";

    // --- Marker rail (issue #6: stand is now `lectern`) --------------------
    // Phosphor ships no icon named "stand" — checked against all 1,512 names
    // in the regular set, where the only matches are `globe-stand` and
    // `standard-definition`. `lectern` is the chosen stand-in: it is the one
    // glyph that reads as an object raised on a stand without also reading
    // as a plant, which is exactly what made `potted-plant` wrong here.
    // Priority is deliberately NOT in this rail. Flower / stand / gift say
    // what is IN the order; priority says how urgent the order IS. Two
    // different kinds of fact, so they no longer share a cluster — the flag
    // rides up next to the open button, where triage information belongs.
    let priority_html = "";
    if (priority) {
        priority_html =
            `<span class="so-priority ${priority_class}" title="${__("Priority")}: ${narjes_escape(priority)}">` +
            narjes_icon("flag-fill", { size: "sm" }) +
            `</span>`;
    }

    let markers_html = "";
    if (has_flower) {
        markers_html += `<span class="so-marker mk-flower" title="${__("Contains Flower")}">` +
            narjes_icon("flower-fill", { size: "sm" }) + `</span>`;
    }
    if (has_stand) {
        markers_html += `<span class="so-marker mk-stand" title="${__("Contains Stand")}">` +
            narjes_icon("lectern-fill", { size: "sm" }) + `</span>`;
    }
    if (has_gift) {
        markers_html += `<span class="so-marker mk-gift" title="${__("Gift")}">` +
            narjes_icon("gift-fill", { size: "sm" }) + `</span>`;
    }

    // --- Meta rows (only those with a value) ---
    let meta_html = "";
    if (username) meta_html += `<div class="so-info-row">@${narjes_escape(username)}</div>`;
    if (delivery_id) meta_html += `<div class="so-info-row">${narjes_escape(delivery_id)}</div>`;
    if (delivery_day) meta_html += `<div class="so-info-row">${narjes_escape(delivery_day)}</div>`;
    if (time_ago) {
        meta_html +=
            `<div class="so-info-row so-time-ago frappe-timestamp"` +
            ` data-timestamp="${narjes_escape(raw_creation)}"` +
            ` title="${narjes_escape(frappe.datetime.str_to_user(raw_creation))}">` +
            `${narjes_escape(time_ago)}</div>`;
    }

    // --- Assignee chip (sits in the space the favourite icon vacated) ---
    const assignee_chip = assignee
        ? `<span class="so-avatar" style="background:${narjes_avatar_tone(assignee)}">` +
              `${narjes_escape(narjes_initials(assignee_name))}</span>` +
          `<span class="so-assignee-name">${narjes_escape(assignee_name.split(" ")[0])}</span>`
        : `<span class="so-avatar so-avatar-empty">${narjes_icon("user-plus", { size: "xs" })}</span>` +
          `<span class="so-assignee-name">${__("Assign")}</span>`;

    // Same rule as the meta rows (issue #11): an order with no value and no
    // markers must not leave an empty band with a divider above it.
    const money_row_html =
        total_html || markers_html
            ? `<div class="so-money-row">` +
                  `<span class="so-total">${total_html}</span>` +
                  `<span class="so-markers">${markers_html}</span>` +
              `</div>`
            : "";

    const form_link = `/app/sales-order/${encodeURIComponent(card.name)}`;

    // --- Full Card HTML ---
    const html = `
        <div class="kanban-card-wrapper" data-name="${encodeURIComponent(card.name)}">
            <div class="so-kanban-card" data-owner="${narjes_escape(owner_raw)}" data-assignee="${narjes_escape(assignee)}">
                <div class="so-head">
                    <label class="so-select-wrap" title="${__("Select for bulk move")}">
                        <input type="checkbox" class="so-card-select" aria-label="${__("Select ticket")}">
                    </label>
                    <div class="so-title-row">
                        <a href="${form_link}" title="${narjes_escape(customer)}">${narjes_escape(customer)}</a>
                    </div>
                    ${priority_html}
                    <a class="so-open-btn" href="${form_link}"
                       title="${__("Open Sales Order")}" aria-label="${__("Open Sales Order")}">
                        ${narjes_icon("arrow-square-out", { size: "sm" })}
                    </a>
                </div>
                <div class="so-meta">${meta_html}</div>
                ${money_row_html}
                <div class="so-foot">
                    <button type="button" class="so-assignee${assignee ? "" : " is-unassigned"}"
                            title="${__("Change assignee")}">${assignee_chip}</button>
                    <span class="so-foot-spacer"></span>
                    <span class="so-creator-badge" title="${__("Created by")}: ${narjes_escape(owner_display)}">${narjes_escape(owner_display)}</span>
                </div>
            </div>
        </div>
    `;

    const $card = $(html).appendTo(wrapper);

    // Frappe repaints columns wholesale, so a freshly rendered card has to read
    // its checked state back out of the selection Set rather than trusting the
    // DOM it just replaced (see SECTION 8).
    if (NARJES_SELECTED.has(card.name)) {
        $card.find(".so-card-select").prop("checked", true);
        $card.addClass("is-selected");
    }

    // Open in an overlay instead of navigating away (issue #4). They stay real
    // anchors — same href, so middle-click, ⌘-click and "copy link" all still
    // do the ordinary thing — and only a plain left click is intercepted.
    $card.find(".so-open-btn, .so-title-row a").on("click", function (e) {
        e.stopPropagation();
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.which === 2) return;
        e.preventDefault();
        narjes_open_order_overlay(card.name);
    });

    // Assignee picker (issue #5)
    $card.find(".so-assignee").on("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        narjes_open_assignee_picker($(this), card, assigned);
    });

    // Undraggable without write access
    if (!frappe.model.can_write("Sales Order")) {
        $card.find(".so-kanban-card").css("cursor", "default");
    }

    return { $card };
}

// SECTION 4b: Sales Order Overlay
// --------------------------------------------------------
// Opens the real Sales Order form on top of the board (issue #4).
//
// It is an iframe onto /app/sales-order/<name>, which is the only way to get
// the form EXACTLY as it renders in a full window — every tab, the gallery,
// the Submit button, all of its own client scripts — without re-implementing
// any of it. Frappe serves the desk with X-Frame-Options: SAMEORIGIN, so a
// same-origin frame is allowed.
//
// Crucially the board is never navigated away from: the kanban DOM, its
// scroll position and the collapsed columns are all still sitting there
// untouched when the overlay closes, so closing costs nothing and reloads
// nothing.

function narjes_close_order_overlay() {
    const $o = $("#narjes-order-overlay");
    if (!$o.length) return;
    const poll = $o.data("narjes-state-poll");
    if (poll) clearInterval(poll);
    $o.addClass("is-closing");
    $(document).off(".narjes_overlay");
    setTimeout(() => $o.remove(), 160);
}

// Reach the form living inside the overlay frame. Same-origin, so its
// cur_frm is directly callable — which is what lets the overlay drive Save
// and Submit without the desk header the panel replaces.
function narjes_overlay_frm() {
    const iframe = $("#narjes-order-overlay iframe")[0];
    try {
        return (iframe && iframe.contentWindow && iframe.contentWindow.cur_frm) || null;
    } catch (e) {
        return null;
    }
}

function narjes_overlay_save(submit) {
    const frm = narjes_overlay_frm();
    if (!frm) return;

    // savesubmit() runs its own confirmation dialog; save() does not.
    //
    // No success toast here on purpose. The form inside the frame already
    // raises its own "Saved" alert, and adding a second one in the parent
    // document put two identical toasts on screen at once. Failures are
    // likewise reported by the frame, next to the field that caused them.
    return submit ? frm.savesubmit() : frm.save();
}

function narjes_open_order_overlay(docname) {
    narjes_close_order_overlay();

    const url = `/app/sales-order/${encodeURIComponent(docname)}`;
    const $overlay = $(`
        <div id="narjes-order-overlay" role="dialog" aria-modal="true"
             aria-label="${__("Sales Order")} ${narjes_escape(docname)}">
            <div class="narjes-overlay-panel">
                <div class="narjes-overlay-bar">
                    <span class="narjes-overlay-title">${narjes_escape(docname)}</span>
                    <span class="narjes-overlay-status"></span>
                    <span class="narjes-overlay-spacer"></span>
                    <button type="button" class="narjes-overlay-btn narjes-overlay-save">
                        ${__("Save")}
                    </button>
                    <button type="button" class="narjes-overlay-btn narjes-overlay-submit is-primary" hidden>
                        ${__("Submit")}
                    </button>
                    <button type="button" class="narjes-overlay-close"
                            title="${__("Close")}" aria-label="${__("Close")}">
                        ${narjes_icon("x", { size: "sm" })}
                    </button>
                </div>
                <div class="narjes-overlay-loading">${__("Loading…")}</div>
                <iframe class="narjes-overlay-frame" src="${url}"
                        title="${__("Sales Order")} ${narjes_escape(docname)}"></iframe>
            </div>
        </div>
    `).appendTo(document.body);

    const iframe = $overlay.find("iframe")[0];
    iframe.addEventListener("load", () => {
        $overlay.addClass("is-loaded");
        // Strip the desk chrome inside the frame — navbar, sidebar and the
        // app's own breadcrumbs are redundant when the form is already
        // presented as a panel. Same-origin, so this is just a class on the
        // frame's <body>; the styling lives in the theme (_kanban.scss).
        try {
            iframe.contentDocument.body.classList.add("narjes-embedded-form");

            // ⌘S / Ctrl+S while the cursor is inside the frame. Frappe's own
            // handler resolves through the page header's primary action, which
            // the panel hides — so with the header gone the shortcut silently
            // did nothing. Bind our own inside the frame and save directly.
            iframe.contentDocument.addEventListener("keydown", (e) => {
                if ((e.metaKey || e.ctrlKey) && (e.key === "s" || e.key === "S")) {
                    e.preventDefault();
                    e.stopPropagation();
                    narjes_overlay_save(false);
                } else if (e.key === "Escape") {
                    narjes_close_order_overlay();
                }
            }, true);
        } catch (e) {
            /* cross-origin would mean a redirect to login — leave it alone */
        }
    });

    // Keep the bar honest about what the form can do right now.
    const $save = $overlay.find(".narjes-overlay-save");
    const $submit = $overlay.find(".narjes-overlay-submit");
    const $status = $overlay.find(".narjes-overlay-status");

    const sync_state = () => {
        const frm = narjes_overlay_frm();
        if (!frm || !frm.doc) return;
        const dirty = !!frm.doc.__unsaved;
        const docstatus = frm.doc.docstatus;

        $save.prop("disabled", !dirty).text(dirty ? __("Save") : __("Saved"));
        // Submit is only meaningful on a saved draft.
        $submit.prop("hidden", !(docstatus === 0 && !dirty && !frm.is_new()));
        $status
            .text(docstatus === 1 ? __("Submitted") : docstatus === 2 ? __("Cancelled")
                : dirty ? __("Not saved") : __("Draft"))
            .attr("data-state", docstatus === 1 ? "submitted"
                : docstatus === 2 ? "cancelled" : dirty ? "dirty" : "draft");
    };
    $overlay.data("narjes-state-poll", setInterval(sync_state, 500));

    $save.on("click", () => narjes_overlay_save(false));
    $submit.on("click", () => narjes_overlay_save(true));

    // Click anywhere around the panel closes it.
    $overlay.on("click", (e) => {
        if (e.target === $overlay[0]) narjes_close_order_overlay();
    });
    $overlay.find(".narjes-overlay-close").on("click", narjes_close_order_overlay);

    // ...and the same shortcut when focus is still on the board behind it.
    $(document).on("keydown.narjes_overlay", (e) => {
        if (e.key === "Escape") {
            narjes_close_order_overlay();
        } else if ((e.metaKey || e.ctrlKey) && (e.key === "s" || e.key === "S")) {
            e.preventDefault();
            narjes_overlay_save(false);
        }
    });
}

// SECTION 5: Assignee Picker
// --------------------------------------------------------
// Writes through Frappe's standard assignment API (ToDo + _assign), so the
// board and the form sidebar stay in agreement and normal assignment
// notifications still fire.

let NARJES_ASSIGNABLE = null;
let NARJES_ASSIGNABLE_REQ = null;

// Doubles as the name cache primer. frappe.boot.user_info ships with ONLY
// the logged-in user in it (boot.py → get_user_info adds frappe.session.user
// and nobody else), which is the real reason the old card fell back to the
// email local-part for everyone else. Loading the staff list once at board
// boot means the very first paint already has full names.
function narjes_get_assignable_users() {
    if (NARJES_ASSIGNABLE) return Promise.resolve(NARJES_ASSIGNABLE);
    if (NARJES_ASSIGNABLE_REQ) return NARJES_ASSIGNABLE_REQ;

    NARJES_ASSIGNABLE_REQ = frappe.db
        .get_list("User", {
            filters: { enabled: 1, user_type: "System User" },
            fields: ["name", "full_name", "user_image"],
            order_by: "full_name asc",
            limit: 100,
        })
        .then((rows) => {
            NARJES_ASSIGNABLE = (rows || []).filter((u) => u.name !== "Administrator");
            NARJES_ASSIGNABLE_REQ = null;

            const patch = {};
            NARJES_ASSIGNABLE.forEach((u) => {
                patch[u.name] = {
                    fullname: u.full_name || u.name,
                    image: u.user_image,
                    name: u.name,
                };
            });
            if (Object.keys(patch).length) frappe.update_user_info(patch);

            return NARJES_ASSIGNABLE;
        })
        .catch(() => {
            // No read access to User (or the call failed): fall back to
            // whatever names the boot cache already knows, so the picker
            // degrades to a short list instead of an empty box.
            NARJES_ASSIGNABLE_REQ = null;
            NARJES_ASSIGNABLE = Object.keys(frappe.boot.user_info || {})
                .filter((u) => u !== "Administrator" && u.includes("@"))
                .map((u) => ({ name: u, full_name: frappe.boot.user_info[u].fullname }));
            return NARJES_ASSIGNABLE;
        });

    return NARJES_ASSIGNABLE_REQ;
}

function narjes_open_assignee_picker($btn, card, assigned) {
    $(".so-assignee-pop").remove();
    const current = assigned && assigned.length ? assigned[0] : "";

    narjes_get_assignable_users().then((users) => {
        const rows = users
            .map((u) => {
                const nm = u.full_name || u.name;
                const active = u.name === current;
                return (
                    `<button type="button" class="so-pop-item${active ? " is-active" : ""}" data-user="${narjes_escape(u.name)}">` +
                    `<span class="so-avatar" style="background:${narjes_avatar_tone(u.name)}">${narjes_escape(narjes_initials(nm))}</span>` +
                    `<span class="so-pop-name">${narjes_escape(nm)}</span>` +
                    (active ? narjes_icon("check", { size: "xs", class: "so-pop-check" }) : "") +
                    `</button>`
                );
            })
            .join("");

        const $pop = $(
            `<div class="so-assignee-pop" role="dialog" aria-label="${__("Choose assignee")}">` +
                `<div class="so-pop-head">${__("Assign to")}</div>` +
                `<div class="so-pop-list">${rows}</div>` +
                (current
                    ? `<div class="so-pop-sep"></div>` +
                      `<button type="button" class="so-pop-item so-pop-clear" data-user="">` +
                      `<span class="so-avatar so-avatar-empty">${narjes_icon("user-plus", { size: "xs" })}</span>` +
                      `<span class="so-pop-name">${__("Unassign")}</span></button>`
                    : "") +
            `</div>`
        ).appendTo(document.body);

        // Position under the chip, flipping up when it would run off-screen.
        const r = $btn[0].getBoundingClientRect();
        const ph = $pop.outerHeight();
        const pw = $pop.outerWidth();
        let top = r.bottom + 6;
        if (top + ph > window.innerHeight - 8) top = Math.max(8, r.top - ph - 6);
        $pop.css({
            top: top + "px",
            left: Math.max(8, Math.min(r.left, window.innerWidth - pw - 12)) + "px",
        });

        $pop.on("click", ".so-pop-item", function () {
            const user = $(this).attr("data-user");
            close();
            narjes_set_assignee(card, current, user);
        });

        // Dismiss on outside click / Escape. Bind under one namespace and
        // clear it first, so repeatedly opening pickers cannot pile up
        // handlers on document.
        $(document).off(".so_pop");
        const close = () => {
            $pop.remove();
            $(document).off(".so_pop");
        };
        setTimeout(() => {
            $(document).on("click.so_pop", close);
            $(document).on("keydown.so_pop", (e) => {
                if (e.key === "Escape") close();
            });
        }, 0);
        $pop.on("click", (e) => e.stopPropagation());
    });
}

function narjes_set_assignee(card, current, next) {
    if (current === next) return;

    const done = () => {
        frappe.show_alert({
            message: next
                ? __("Assigned to {0}", [narjes_full_name(next)])
                : __("Assignment cleared"),
            indicator: "green",
        });
        // Re-pull the board so the card repaints from the source of truth.
        // (bare `cur_list` would throw before any list view has set it)
        if (window.cur_list && window.cur_list.refresh) window.cur_list.refresh();
    };

    const assign_next = () => {
        if (!next) return done();
        frappe.call({
            method: "frappe.desk.form.assign_to.add",
            args: {
                doctype: "Sales Order",
                name: card.name,
                assign_to: [next],
            },
            callback: (r) => {
                if (!r.exc) done();
            },
        });
    };

    if (current) {
        frappe.call({
            method: "frappe.desk.form.assign_to.remove",
            args: { doctype: "Sales Order", name: card.name, assign_to: current },
            callback: () => assign_next(),
        });
    } else {
        assign_next();
    }
}

// SECTION 6: Column Chrome — live count + collapse
// --------------------------------------------------------
// Frappe rebuilds .kanban-column nodes wholesale (KanbanBoard.make_columns
// empties and re-appends), so decorating them once on load is not enough.
// A MutationObserver on the board re-decorates whatever appears, and a
// second observer per column keeps the count honest.
//
// Counting DOM children rather than reading the kanban store is deliberate:
// the store is module-private inside kanban_board.bundle.js, and the DOM is
// the one thing guaranteed to reflect adds, drops, filters and refreshes
// alike — which is what "live, without a refresh" needs (issue #9).

const NARJES_COLLAPSE_KEY = "narjes_kanban_collapsed";

function narjes_collapsed_set() {
    try {
        return new Set(JSON.parse(localStorage.getItem(NARJES_COLLAPSE_KEY) || "[]"));
    } catch (e) {
        return new Set();
    }
}

function narjes_store_collapsed(set) {
    try {
        localStorage.setItem(NARJES_COLLAPSE_KEY, JSON.stringify(Array.from(set)));
    } catch (e) {
        /* private browsing — collapse just won't persist */
    }
}

// Frappe repaints a column by emptying .kanban-cards and re-appending, so a
// naive observer sees a transient 0 and the pill flickers 3 → 0 → 3 on every
// refresh. Coalescing to the next frame lets the DOM settle first, so the
// count only ever moves when it genuinely changed.
function narjes_update_count($column) {
    const col = $column[0];
    if (!col || col._narjes_count_queued) return;
    col._narjes_count_queued = true;

    requestAnimationFrame(() => {
        col._narjes_count_queued = false;
        const n = $column.find(".kanban-cards .kanban-card-wrapper").length;
        const $pill = $column.find(".so-column-count");
        if (!$pill.length) return;
        narjes_sync_column_toggle(0, col);
        if ($pill.text() !== String(n)) {
            $pill.text(n);
            $pill.addClass("is-bumped");
            setTimeout(() => $pill.removeClass("is-bumped"), 550);
        }
    });
}

function narjes_decorate_column(column) {
    const $column = $(column);
    if ($column.hasClass("add-new-column")) return;

    const $header = $column.find(".kanban-column-header").first();
    if (!$header.length) return;

    // Test for the button itself rather than a "decorated" flag on the
    // element. A flag goes stale the moment Frappe re-renders the header
    // underneath us — the flag still says decorated, the button is gone, and
    // the collapse control silently vanishes until a full page reload. Asking
    // the DOM what is actually there cannot drift.
    if ($header.find(".so-column-collapse").length) return;

    const title = $column.attr("data-column-value") || "";

    // Live ticket count (issue #9)
    if (!$header.find(".so-column-count").length) {
        $column.find(".kanban-column-title").before(
            `<label class="so-select-wrap so-column-select" title="${__("Select all in this column")}">
                <input type="checkbox" class="so-column-select-all" aria-label="${__("Select all in this column")}">
            </label>`
        );
        $column.find(".kanban-column-title").after(`<span class="so-column-count">0</span>`);
    }

    // Collapse toggle (issue #8)
    const $toggle = $(
        `<button type="button" class="so-column-collapse" title="${__("Collapse column")}" aria-label="${__("Collapse column")}">` +
            narjes_icon("caret-double-left", { size: "sm" }) +
        `</button>`
    );
    $header.append($toggle);

    const apply = (collapsed, persist) => {
        $column.toggleClass("so-collapsed", collapsed);
        $toggle
            .html(narjes_icon(collapsed ? "caret-double-right" : "caret-double-left", { size: "sm" }))
            .attr("title", collapsed ? __("Expand column") : __("Collapse column"))
            .attr("aria-label", collapsed ? __("Expand column") : __("Collapse column"));
        if (persist) {
            const set = narjes_collapsed_set();
            collapsed ? set.add(title) : set.delete(title);
            narjes_store_collapsed(set);
        }
    };

    $toggle.on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        apply(!$column.hasClass("so-collapsed"), true);
    });

    // Restore the user's last state for this column
    if (narjes_collapsed_set().has(title)) apply(true, false);

    // Keep the count live as cards come and go
    const cards_el = $column.find(".kanban-cards")[0];
    if (cards_el) {
        new MutationObserver(() => narjes_update_count($column)).observe(cards_el, {
            childList: true,
        });
    }
    narjes_update_count($column);
}

function narjes_decorate_all() {
    document
        .querySelectorAll(".kanban .kanban-column")
        .forEach(narjes_decorate_column);
}

let NARJES_DECORATE_QUEUED = false;

function narjes_queue_decorate() {
    if (NARJES_DECORATE_QUEUED) return;
    NARJES_DECORATE_QUEUED = true;
    requestAnimationFrame(() => {
        NARJES_DECORATE_QUEUED = false;
        narjes_decorate_all();
    });
}

function narjes_watch_board() {
    const board = document.querySelector(".kanban");
    if (!board) return;

    // Watch the board's PARENT, not the board. Frappe rebuilds .kanban itself
    // (KanbanBoard.prepare re-renders the template whenever the wrapper has
    // been emptied), which silently threw away an observer bound to the old
    // element — the collapse buttons then stayed missing until a full page
    // reload. The parent survives those rebuilds, so the observer does too.
    const host = board.parentElement || board;
    if (!host._narjes_watched) {
        host._narjes_watched = true;
        new MutationObserver(narjes_queue_decorate).observe(host, {
            childList: true,
            subtree: true,
        });
    }

    narjes_decorate_all();
}

// The board is built asynchronously after the route settles; poll briefly
// rather than racing it.
function narjes_kanban_boot() {
    // Warm the staff list before the cards land, so creator stamps and
    // assignee chips render with full names on the first paint rather than
    // flashing an email and being patched a round trip later.
    narjes_get_assignable_users();

    let tries = 0;
    const timer = setInterval(() => {
        if (document.querySelector(".kanban .kanban-column")) {
            narjes_watch_board();
            clearInterval(timer);
        } else if (++tries > 40) {
            clearInterval(timer);
        }
    }, 150);
}

// SECTION 7: Intercept KanbanBoardCard Assignment
// --------------------------------------------------------
// The kanban_board.bundle.js loads LAZILY (as required_libs) and assigns
// frappe.views.KanbanBoardCard AFTER this script runs. Object.defineProperty
// intercepts the setter so the moment the bundle sets it, we substitute our
// card — but ONLY for Sales Order. Other doctypes get the original.

if (!frappe._narjes_kanban_intercepted) {
    frappe._narjes_kanban_intercepted = true;

    let _original_KanbanBoardCard = frappe.views.KanbanBoardCard; // may be undefined initially

    Object.defineProperty(frappe.views, "KanbanBoardCard", {
        get: function () {
            return function (card, wrapper) {
                if (card && card.doctype === "Sales Order") {
                    return narjes_custom_card(card, wrapper);
                }
                if (_original_KanbanBoardCard) {
                    return _original_KanbanBoardCard(card, wrapper);
                }
            };
        },
        set: function (val) {
            _original_KanbanBoardCard = val;
        },
        configurable: true,
        enumerable: true,
    });
}

// SECTION 8: Force Backend to Fetch Custom Fields
// --------------------------------------------------------
// KanbanView.set_fields() reads board.fields to decide which columns to
// SELECT. Patch it so the card's fields are always present even if the
// board document drifts. (_assign, owner and creation are already added by
// Frappe's own set_fields.)

frappe.router.on("change", () => {
    if (frappe.views && frappe.views.KanbanView && !frappe.views.KanbanView._narjes_fields_patched) {
        frappe.views.KanbanView._narjes_fields_patched = true;
        const orig_set_fields = frappe.views.KanbanView.prototype.set_fields;
        frappe.views.KanbanView.prototype.set_fields = function () {
            orig_set_fields.apply(this);
            if (this.doctype === "Sales Order") {
                const needed = [
                    "customer", "username", "delivery_id", "delivery_date",
                    "gift", "has_flower", "has_stand", "priority", "owner",
                    "creation", "grand_total", "currency",
                ];
                needed.forEach((f) => {
                    this._add_field(f);
                });
            }
        };
    }

    if (frappe.get_route()[0] === "List" && frappe.get_route()[2] === "Kanban") {
        narjes_kanban_boot();
    }
});

// SECTION 9: ListView Settings (redirect to Kanban)
// --------------------------------------------------------
frappe.listview_settings["Sales Order"] = {
    onload: function (listview) {
        if (frappe.get_route()[2] !== "Kanban") {
            frappe.set_route("List", "Sales Order", "Kanban", "Order Phases");
        } else {
            narjes_kanban_boot();
        }
    },
};

// SECTION 8: Multi-select and bulk phase moves
// --------------------------------------------------------
// A day's tidying is usually "these four all went out for delivery", but the
// board can only drag one card at a time. This adds a checkbox per card, a
// select-all per column, and one bulk move for the whole selection.
//
// Selection lives in a module-level Set keyed by docname rather than on the
// DOM nodes, because Frappe repaints columns wholesale (see SECTION 6) — a
// checked box on a node that gets replaced would silently lose its state
// mid-selection. Re-rendered cards read their state back out of the Set.

const NARJES_SELECTED = new Set();

function narjes_selection_changed() {
    // Keep every rendered checkbox in step with the Set, including cards that
    // were repainted while the selection was being built.
    $(".kanban-card-wrapper").each(function () {
        const name = decodeURIComponent($(this).attr("data-name") || "");
        const $box = $(this).find(".so-card-select");
        if (!$box.length) return;
        const on = NARJES_SELECTED.has(name);
        $box.prop("checked", on);
        $(this).toggleClass("is-selected", on);
    });

    $(".kanban-column").each(narjes_sync_column_toggle);
    narjes_render_bulk_bar();
}

// Names of the cards currently rendered in one column.
function narjes_column_names($column) {
    return $column
        .find(".kanban-cards .kanban-card-wrapper")
        .map(function () {
            return decodeURIComponent($(this).attr("data-name") || "");
        })
        .get()
        .filter(Boolean);
}

function narjes_sync_column_toggle(_i, column) {
    const $column = $(column);
    const $toggle = $column.find(".so-column-select-all");
    if (!$toggle.length) return;

    const names = narjes_column_names($column);
    const chosen = names.filter((n) => NARJES_SELECTED.has(n));

    $toggle.prop("checked", names.length > 0 && chosen.length === names.length);
    // Partial selection reads as indeterminate rather than unchecked, so the
    // header never claims "nothing selected" while cards below it are ticked.
    $toggle.prop("indeterminate", chosen.length > 0 && chosen.length < names.length);
    $toggle.prop("disabled", names.length === 0);
}

function narjes_toggle_column($column, on) {
    narjes_column_names($column).forEach((name) => {
        if (on) NARJES_SELECTED.add(name);
        else NARJES_SELECTED.delete(name);
    });
    narjes_selection_changed();
}

// --- the floating action bar ---

function narjes_render_bulk_bar() {
    const count = NARJES_SELECTED.size;
    let $bar = $("#narjes-bulk-bar");

    if (!count) {
        $bar.remove();
        return;
    }

    if (!$bar.length) {
        $bar = $(`
            <div id="narjes-bulk-bar" role="region" aria-label="${__("Bulk actions")}">
                <span class="nbb-count"></span>
                <span class="nbb-actions">
                    <button type="button" class="btn btn-primary btn-sm nbb-move">${__("Move to...")}</button>
                    <button type="button" class="btn btn-default btn-sm nbb-clear">${__("Clear")}</button>
                </span>
            </div>
        `).appendTo(document.body);

        $bar.on("click", ".nbb-clear", () => {
            NARJES_SELECTED.clear();
            narjes_selection_changed();
        });
        $bar.on("click", ".nbb-move", narjes_prompt_bulk_move);
    }

    $bar.find(".nbb-count").text(
        count === 1 ? __("1 ticket selected") : __("{0} tickets selected", [count])
    );
}

function narjes_board_columns() {
    return $(".kanban-column")
        .not(".add-new-column")
        .map(function () {
            return $(this).attr("data-column-value");
        })
        .get()
        .filter(Boolean);
}

function narjes_prompt_bulk_move() {
    const names = Array.from(NARJES_SELECTED);
    const columns = narjes_board_columns();

    const d = new frappe.ui.Dialog({
        title: __("Move {0} ticket(s)", [names.length]),
        fields: [
            {
                fieldname: "phase",
                label: __("Move to column"),
                fieldtype: "Select",
                options: columns.join("\n"),
                reqd: 1,
            },
            {
                fieldname: "warning",
                fieldtype: "HTML",
            },
        ],
        primary_action_label: __("Move"),
        primary_action(values) {
            d.hide();
            narjes_run_bulk_move(names, values.phase);
        },
    });

    // Done and Cancelled are not ordinary column moves — one submits every
    // selected order, the other cancels them. Say so before, not after.
    d.fields_dict.phase.$input && d.fields_dict.phase.$input.on("change", () => {
        const phase = d.get_value("phase");
        let msg = "";
        if (phase === "Done") {
            msg = __(
                "Moving to Done SUBMITS these orders. Any that fail (short stock, for example) stay where they are and will be listed."
            );
        } else if (phase === "Cancelled") {
            msg = __("Moving to Cancelled CANCELS these orders and their linked documents.");
        }
        d.fields_dict.warning.$wrapper.html(
            msg ? `<div class="alert alert-warning" style="margin:0">${msg}</div>` : ""
        );
    });

    d.show();
}

function narjes_run_bulk_move(names, phase) {
    frappe.dom.freeze(__("Moving {0} ticket(s)...", [names.length]));
    frappe.call({
        method: "narjes_custom.api.bulk_move_phase",
        args: { docnames: JSON.stringify(names), phase },
        callback: (r) => {
            frappe.dom.unfreeze();
            const res = r.message || { moved: [], failed: [] };

            // Only the orders that actually moved leave the selection, so a
            // retry after fixing stock does not require re-ticking everything.
            res.moved.forEach((n) => NARJES_SELECTED.delete(n));

            if (res.failed.length) {
                const rows = res.failed
                    .map(
                        (f) =>
                            `<li><b>${frappe.utils.escape_html(f.name)}</b>: ${frappe.utils.escape_html(
                                f.error
                            )}</li>`
                    )
                    .join("");
                frappe.msgprint({
                    title: __("{0} moved, {1} could not", [res.moved.length, res.failed.length]),
                    message: `<ul style="margin:0;padding-inline-start:18px">${rows}</ul>`,
                    indicator: res.moved.length ? "orange" : "red",
                });
            } else {
                frappe.show_alert({
                    message: __("Moved {0} ticket(s)", [res.moved.length]),
                    indicator: "green",
                });
            }

            setTimeout(() => location.reload(), res.failed.length ? 3000 : 600);
        },
        error: () => frappe.dom.unfreeze(),
    });
}

// --- wiring: delegated handlers survive Frappe's repaints ---

$(document).on("change", ".so-card-select", function (e) {
    e.stopPropagation();
    const name = decodeURIComponent($(this).closest(".kanban-card-wrapper").attr("data-name") || "");
    if (!name) return;
    if (this.checked) NARJES_SELECTED.add(name);
    else NARJES_SELECTED.delete(name);
    narjes_selection_changed();
});

// The checkbox sits inside a draggable card; without this a tick starts a drag.
$(document).on("mousedown touchstart pointerdown", ".so-card-select, .so-select-wrap", function (e) {
    e.stopPropagation();
});

$(document).on("change", ".so-column-select-all", function (e) {
    e.stopPropagation();
    narjes_toggle_column($(this).closest(".kanban-column"), this.checked);
});
