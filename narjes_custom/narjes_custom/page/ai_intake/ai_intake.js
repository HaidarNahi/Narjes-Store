frappe.pages["ai-intake"].on_page_load = function (wrapper) {
    const AI_INTAKE_CSS = `
    .ai-intake-wrap {
        max-width: 900px;
        margin: 30px auto;
        padding: 0 16px;
        font-family: var(--font-stack);
        animation: fadeIn 0.3s ease-out;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .ai-intake-card {
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius-lg);
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: var(--shadow-sm);
        transition: box-shadow 0.2s;
    }
    .ai-intake-card:hover {
        box-shadow: var(--shadow-base);
    }
    .ai-intake-card h4 {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-color);
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border-color);
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .ai-intake-textarea {
        width: 100%;
        min-height: 180px;
        padding: 12px;
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
        font-size: 14px;
        font-family: var(--font-stack);
        resize: vertical;
        background: var(--control-bg);
        color: var(--text-color);
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    .ai-intake-textarea:focus {
        outline: none;
        border-color: var(--primary);
        box-shadow: 0 0 0 3px var(--primary-light);
    }
    .ai-btn-gradient {
        background: linear-gradient(135deg, var(--primary), var(--narjes-fern-strong));
        color: white;
        border: none;
        transition: transform 0.1s, box-shadow 0.2s;
    }
    .ai-btn-gradient:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .ai-intake-btn-process {
        margin-top: 14px;
        padding: 8px 22px;
        font-weight: 600;
        font-size: 14px;
    }
    .ai-match-badge, .ai-status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
    }
    .ai-status-pill {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .ai-match-phone { background: var(--narjes-fern-tint); color: var(--narjes-fern-strong); }
    .ai-match-fuzzy { background: var(--narjes-warning-tint); color: var(--narjes-warning); }
    .ai-match-none { background: var(--narjes-paper-sunken); color: var(--narjes-ink-muted); }
    .ai-status-Draft { background: var(--narjes-paper-sunken); color: var(--narjes-ink); }
    .ai-status-Review { background: #e7e5fb; color: #4c46a3; }

    .ai-notes-box {
        background: #fffbeb;
        border: 1px solid #fbbf24;
        border-radius: var(--border-radius);
        padding: 10px 14px;
        font-size: 13px;
        color: #92400e;
    }
    .ai-notes-box ul { margin: 4px 0 0 16px; padding: 0; }

    .ai-field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
    .ai-field-group label { display: block; font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 4px; }
    .ai-field-group input, .ai-field-group select {
        width: 100%;
        padding: 7px 10px;
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
        font-size: 14px;
        background: var(--control-bg);
        color: var(--text-color);
        transition: border-color 0.2s;
    }
    .ai-field-group input.has-error, .ai-field-group select.has-error {
        border-color: var(--red);
    }
    .ai-error-msg {
        font-size: 11px;
        color: var(--red);
        margin-top: 4px;
        display: none;
    }

    .ai-items-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .ai-items-table th {
        text-align: left;
        padding: 8px 10px;
        background: var(--bg-color);
        color: var(--text-muted);
        font-weight: 600;
        font-size: 12px;
        border-bottom: 2px solid var(--border-color);
    }
    .ai-items-table td { padding: 6px 8px; border-bottom: 1px solid var(--border-color); }
    .ai-items-table input {
        width: 100%; padding: 6px 8px; border: 1px solid var(--border-color);
        border-radius: 4px; font-size: 13px; background: var(--control-bg); color: var(--text-color);
    }
    .ai-items-table input.has-error { border-color: var(--red); }
    .ai-items-table .btn-remove { background: none; border: none; color: var(--red); cursor: pointer; font-size: 18px; padding: 0 4px; }
    .ai-total-row { font-weight: 600; background: var(--bg-light); }

    .ai-autocomplete-wrap { position: relative; }
    .ai-autocomplete-dropdown {
        position: absolute; top: 100%; left: 0; right: 0; z-index: 10;
        background: var(--card-bg); border: 1px solid var(--border-color);
        border-radius: var(--border-radius); box-shadow: var(--shadow-base);
        max-height: 200px; overflow-y: auto; display: none; margin-top: 4px;
    }
    .ai-autocomplete-item {
        padding: 8px 12px; cursor: pointer; border-bottom: 1px solid var(--border-color);
    }
    .ai-autocomplete-item:hover { background: var(--bg-light); }

    .ai-spinner-wrap { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px 0; gap: 16px; }
    .ai-loading-step { font-size: 14px; color: var(--text-muted); transition: color 0.3s; }
    .ai-loading-step.active { color: var(--primary); font-weight: 600; }

    /* intake v2: phone-first customer card */
    .ai-phone-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    .ai-phone-chip {
        display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px;
        border: 1px solid var(--border-color); border-radius: 999px; background: var(--control-bg);
        font-size: 14px; font-weight: 600; direction: ltr;
    }
    .ai-phone-chip .ai-source { font-size: 11px; font-weight: 500; color: var(--text-muted); direction: rtl; }
    .ai-phone-chip.is-off { opacity: 0.5; text-decoration: line-through; }
    .ai-banner { border-radius: var(--border-radius); padding: 10px 14px; margin: 8px 0 12px; font-size: 13px; }
    .ai-banner strong { font-size: 14px; }
    .ai-banner-green { background: var(--narjes-fern-tint, #ecfdf5); color: var(--narjes-fern-strong, #065f46); border: 1px solid #a7f3d0; }
    .ai-banner-blue { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }
    .ai-banner-red { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
    .ai-banner-amber { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }
    .ai-customer-box { border: 1px solid var(--border-color); border-radius: var(--border-radius); padding: 10px 14px; margin: 6px 0; font-size: 13px; }
    .ai-customer-box .ai-cust-name { font-weight: 600; font-size: 14px; }
    .ai-customer-box .ai-cust-meta { color: var(--text-muted); margin-top: 2px; }
    label.ai-customer-box { display: block; cursor: pointer; }
    label.ai-customer-box.is-chosen { border-color: var(--primary); box-shadow: 0 0 0 2px var(--primary-light); }
    .ai-inline-row { display: flex; gap: 8px; align-items: flex-end; flex-wrap: wrap; margin-top: 8px; }
    .ai-inline-row .ai-field-group { flex: 1; min-width: 180px; }
    .ai-link { color: var(--primary); cursor: pointer; font-size: 12px; text-decoration: underline; }
    .ai-muted { color: var(--text-muted); font-size: 12px; }
    .ai-amounts { font-size: 13px; padding: 8px 12px; border-radius: var(--border-radius); background: var(--bg-light); margin-top: 10px; }
    .ai-amounts .ok { color: var(--narjes-fern-strong, #065f46); }
    .ai-amounts .warn { color: #b45309; font-weight: 600; }
    .ai-notes-group { margin-top: 4px; }
    .ai-notes-group.red { color: #991b1b; }
    `;

    const esc = (value) => frappe.utils.escape_html(value === null || value === undefined ? "" : String(value));
    const money = (value) => (Math.round(Number(value) || 0)).toLocaleString("en-US");
    const form_link = (doctype, name) => frappe.utils.get_form_link(doctype, name);

    // Iraq's 18 governorates — must stay in sync with
    // narjes_custom.setup.custom_fields.IRAQ_GOVERNORATES (Customer.governorate
    // and Sales Order.governorate_of_delivery are Select fields).
    const IRAQ_GOVERNORATES = [
        "بغداد", "بابل", "واسط", "ديالى", "الديوانية", "كربلاء", "النجف",
        "ذي قار", "ميسان", "المثنى", "البصرة", "الانبار", "صلاح الدين",
        "كركوك", "نينوى", "اربيل", "سليمانية", "دهوك",
    ];

    function governorate_options_html(selected) {
        let html = `<option value="" ${!selected ? "selected" : ""}>— None —</option>`;
        IRAQ_GOVERNORATES.forEach((gov) => {
            html += `<option value="${esc(gov)}" ${selected === gov ? "selected" : ""}>${esc(gov)}</option>`;
        });
        return html;
    }

    // Must stay in sync with the Customer.channal Select options.
    const CUSTOMER_CHANNELS = ["Instagram", "Facebook", "Whatsapp", "Telegram", "TikTok", "Website"];

    function channel_options_html(selected) {
        let html = `<option value="" ${!selected ? "selected" : ""}>— None —</option>`;
        CUSTOMER_CHANNELS.forEach((channel) => {
            html += `<option value="${esc(channel)}" ${selected === channel ? "selected" : ""}>${esc(channel)}</option>`;
        });
        return html;
    }

    // Same rule as narjes_custom.business_logic.compute_delivery_fee and the
    // Sales Order form's preview: Baghdad pays the Baghdad fee, any other
    // governorate the other fee, none chosen yet means no fee.
    function delivery_fee(governorate) {
        const ns = frappe.boot.narjes_settings || {};
        if (!governorate) return 0;
        return governorate === "بغداد" ? ns.baghdad_delivery_fee || 0 : ns.other_governorate_delivery_fee || 0;
    }

    // Edit distance, used only to suggest ITEM codes when a typed code doesn't
    // exist. Never used for customers.
    function levenshtein(a, b) {
        if (a.length === 0) return b.length;
        if (b.length === 0) return a.length;
        const matrix = [];
        for (let i = 0; i <= b.length; i++) { matrix[i] = [i]; }
        for (let j = 0; j <= a.length; j++) { matrix[0][j] = j; }
        for (let i = 1; i <= b.length; i++) {
            for (let j = 1; j <= a.length; j++) {
                matrix[i][j] = b.charAt(i - 1) === a.charAt(j - 1)
                    ? matrix[i - 1][j - 1]
                    : Math.min(matrix[i - 1][j - 1] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j] + 1);
            }
        }
        return matrix[b.length][a.length];
    }

    function customer_box(summary, extra = "") {
        if (!summary) return "";
        const last = summary.last_order
            ? `Last order: <a href="${esc(form_link("Sales Order", summary.last_order.name))}" target="_blank">${esc(summary.last_order.name)}</a> (${esc(summary.last_order.transaction_date)})`
            : "No orders yet";
        return `
            <div class="ai-cust-name">${esc(summary.customer_name)} <a class="ai-muted" href="${esc(form_link("Customer", summary.name))}" target="_blank">${esc(summary.name)}</a>${summary.disabled ? ` <span class="indicator-pill red">Disabled</span>` : ""}</div>
            <div class="ai-cust-meta" dir="ltr" style="text-align:start;">${(summary.phones || []).map(esc).join(" · ") || "No phone"}</div>
            <div class="ai-cust-meta">${esc(summary.governorate)}${summary.full_address ? " — " + esc(summary.full_address) : ""}</div>
            <div class="ai-cust-meta">${last}</div>
            ${extra}`;
    }

    class AIOrderIntakePage {
        constructor(page, wrapper) {
            this.page = page;
            this.wrapper = wrapper;
            this.data = null;
            this.item_catalog = [];
            // One delegated handler for every autocomplete dropdown on the
            // page, instead of one per item row that was never removed.
            $(document).off("click.aiIntake").on("click.aiIntake", (e) => {
                if (!$(e.target).closest(".ai-autocomplete-wrap").length) {
                    $(this.wrapper).find(".ai-autocomplete-dropdown").hide();
                }
            });
            this.render_intake_screen();
        }

        get $main() {
            return $(this.wrapper).find(".layout-main-section");
        }

        // ------------------------------------------------------------ input

        render_intake_screen() {
            this.data = null;
            this.$main.html(`
                <div class="ai-intake-wrap">
                    <div class="ai-intake-card">
                        <h4>${narjes_icon('clipboard-text', {size: 'md'})} Paste Order Text</h4>
                        <p style="font-size:13px;color:var(--text-muted);margin-bottom:12px;">
                            Paste the customer's order form. The customer is found by the phone number in the 📞 field —
                            names are never used to decide who the customer is.
                        </p>
                        <textarea class="ai-intake-textarea" id="ai-raw-text" dir="auto"
                            placeholder="👤 اسم الزبون: …&#10;📞 رقم الهاتف: …"></textarea>
                        <br/>
                        <button class="btn ai-btn-gradient ai-intake-btn-process" id="ai-process-btn">
                            ${narjes_icon('sparkle')} Extract & Match
                        </button>
                        <button class="btn btn-default" id="ai-clear-btn" style="margin-top:14px;margin-inline-start:10px;">Clear</button>
                        <span class="ai-muted" style="margin-inline-start:10px;">Ctrl/⌘ + Enter</span>
                    </div>
                </div>
            `);
            $("#ai-process-btn").on("click", () => this.handle_process());
            $("#ai-clear-btn").on("click", () => $("#ai-raw-text").val("").focus());
            $("#ai-raw-text").on("keydown", (e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === "Enter") this.handle_process();
            });
        }

        handle_process(force_new = 0, text = null) {
            const raw_text = text !== null ? text : ($("#ai-raw-text").val() || "").trim();
            if (!raw_text) {
                frappe.msgprint({ message: "Please paste some order text first.", indicator: "orange" });
                return;
            }
            this.last_text = raw_text;
            this.show_spinner("Reading the order…");
            frappe.call({
                method: "narjes_custom.ai_intake.api.process_intake",
                args: { raw_text, force_new },
                callback: (r) => {
                    this.clear_spinner_interval();
                    if (r.exc) { this.show_error(r.exc); return; }
                    const data = r.message;
                    if (data.duplicate) return this.show_duplicate_warning(data);
                    if (data.status === "Failed") return this.show_extraction_failed(data);
                    this.start_review(data);
                },
                error: (err) => {
                    this.clear_spinner_interval();
                    this.show_error(String(err && err.message ? err.message : err || "Request failed"));
                },
            });
        }

        // ------------------------------------------------------------ review state

        start_review(data) {
            this.data = data;
            this.item_catalog = data.item_catalog || [];
            const phones = (data.phones || []).map((p) => p.e164);
            this.state = {
                entries: data.phones || [],   // phones shown as chips
                phones,                       // the ones kept for the order
                typed: false,                 // phones typed by the reviewer
                override_open: false,
                override_reason: "",
                phones_confirmed: false,
                resolution: data.resolution,
                customer: null,
                mode: null,
                add_extra: [],
                old_phone: "",
                old_customer: null,
            };
            this.reset_mode();
            this.render_review_screen();
        }

        reset_mode() {
            const res = this.state.resolution || {};
            this.state.add_extra = [];
            this.state.old_customer = null;
            this.state.old_phone = "";
            if (res.status === "MATCHED") {
                this.state.mode = "matched";
                this.state.customer = res.customer;
            } else if (res.status === "NEW") {
                this.state.mode = "new";
                this.state.customer = null;
            } else {
                this.state.mode = res.status === "CONFLICT" ? "pick" : null;
                this.state.customer = null;
            }
        }

        lookup(phones, { typed = false } = {}) {
            return new Promise((resolve) => {
                frappe.call({
                    method: "narjes_custom.ai_intake.api.lookup_phones",
                    args: { intake_name: this.data.intake_name, phones: JSON.stringify(phones) },
                    callback: (r) => {
                        const res = r.message || {};
                        if (!res.ok) {
                            frappe.msgprint({
                                title: "Not a phone number",
                                message: `${(res.invalid || []).map(esc).join(", ")} is not a valid phone number.`,
                                indicator: "red",
                            });
                            return resolve(false);
                        }
                        if (typed) {
                            this.state.typed = true;
                            this.state.entries = res.phones;
                        } else {
                            const owners = Object.fromEntries((res.phones || []).map((p) => [p.e164, p.owners]));
                            this.state.entries = this.state.entries.map((p) => ({ ...p, owners: owners[p.e164] || p.owners }));
                        }
                        this.state.phones = (res.phones || []).map((p) => p.e164);
                        this.state.resolution = res.resolution;
                        this.reset_mode();
                        this.render_customer_card();
                        resolve(true);
                    },
                });
            });
        }

        // ------------------------------------------------------------ review screen

        render_review_screen() {
            const data = this.data;
            const ex = data.extracted || {};
            const items = ex.order_items || [];
            const statusClass = "ai-status-" + (data.status === "Needs Review" ? "Review" : "Draft");

            this.$main.html(`
                <div class="ai-intake-wrap">
                    <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;justify-content:space-between;flex-wrap:wrap;">
                        <div style="display:flex;align-items:center;gap:12px;">
                            <button class="btn btn-default btn-sm" id="ai-back-btn">${narjes_icon('arrow-left', {size: 'xs'})} Back</button>
                            <h3 style="margin:0;font-size:16px;">Review Order</h3>
                            <span class="ai-status-pill ${statusClass}">${esc(data.status)}</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:10px;">
                            <a class="ai-muted" href="${esc(form_link("AI Order Intake", data.intake_name))}" target="_blank">${esc(data.intake_name)}</a>
                            <button class="btn btn-default btn-sm" id="ai-discard-btn">Discard</button>
                        </div>
                    </div>

                    ${this.notes_html()}

                    <div class="ai-intake-card" id="ai-customer-card"></div>

                    <div class="ai-intake-card">
                        <h4>${narjes_icon('package', {size: 'md'})} Order Information</h4>
                        <div class="ai-field-row">
                            <div class="ai-field-group">
                                <label>Delivery Date</label>
                                <input type="date" id="ai-delivery-date" value="${esc(ex.delivery_date || "")}"/>
                            </div>
                            <div class="ai-field-group">
                                <label>Currency</label>
                                <select id="ai-currency">
                                    <option value="IQD" ${(ex.currency || "IQD") === "IQD" ? "selected" : ""}>IQD</option>
                                    <option value="USD" ${ex.currency === "USD" ? "selected" : ""}>USD</option>
                                </select>
                            </div>
                        </div>
                        <div class="ai-field-row">
                            <div class="ai-field-group">
                                <label>Priority</label>
                                <select id="ai-priority">
                                    <option value="">— None —</option>
                                    ${["High", "Medium", "Low"].map((p) => `<option value="${p}" ${ex.priority === p ? "selected" : ""}>${p}</option>`).join("")}
                                </select>
                            </div>
                            <div class="ai-field-group">
                                <label>Governorate of Delivery</label>
                                <select id="ai-gov-delivery">${governorate_options_html(data.prefill.governorate || ex.governorate)}</select>
                            </div>
                        </div>
                        <div class="ai-field-row">
                            <div class="ai-field-group">
                                <label>Discount Amount</label>
                                <input type="number" id="ai-discount-amount" value="${esc(ex.discount_amount || data.amounts.discount || 0)}" min="0"/>
                            </div>
                            <div class="ai-field-group">
                                <label>Custom Details</label>
                                <input type="text" id="ai-custom-details" value="${esc(ex.custom_details || "")}" dir="auto" placeholder="Any extra unstructured details..."/>
                            </div>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;margin-top:4px;">
                            <input type="checkbox" id="ai-gift" ${ex.gift ? "checked" : ""}/>
                            <label for="ai-gift" style="font-size:14px;cursor:pointer;font-weight:600;">${narjes_icon('gift', {size: 'xs'})} Mark as Gift Order</label>
                        </div>
                    </div>

                    <div class="ai-intake-card">
                        <h4>${narjes_icon('shopping-bag', {size: 'md'})} Items</h4>
                        <table class="ai-items-table" id="ai-items-table">
                            <thead>
                                <tr>
                                    <th style="width:25%;">Item Code</th>
                                    <th style="width:25%;">Description</th>
                                    <th style="width:10%;">Qty</th>
                                    <th style="width:15%;">Unit Price</th>
                                    <th style="width:15%;">Amount</th>
                                    <th style="width:20%;">Notes</th>
                                    <th style="width:5%;"></th>
                                </tr>
                            </thead>
                            <tbody id="ai-items-tbody"></tbody>
                            <tfoot>
                                <tr class="ai-total-row">
                                    <td colspan="4" style="text-align:end;">Total:</td>
                                    <td id="ai-grand-total">0</td>
                                    <td colspan="2"></td>
                                </tr>
                            </tfoot>
                        </table>
                        <button class="btn btn-default btn-xs" id="ai-add-item-btn" style="margin-top:12px;">+ Add row</button>
                        <div class="ai-amounts" id="ai-amounts"></div>
                    </div>

                    <div style="display:flex;gap:12px;margin-top:4px;margin-bottom:40px;">
                        <button class="btn ai-btn-gradient btn-lg" id="ai-confirm-btn">
                            ${narjes_icon('check-circle')} Confirm &amp; Create Order
                        </button>
                        <button class="btn btn-default btn-lg" id="ai-cancel-btn">Cancel</button>
                    </div>
                </div>
            `);

            (items.length ? items : [{}]).forEach((item) => this.add_item_row(item));
            this.render_customer_card();
            this.update_totals();

            $("#ai-back-btn, #ai-cancel-btn").on("click", () => this.render_intake_screen());
            $("#ai-discard-btn").on("click", () => this.handle_discard());
            $("#ai-add-item-btn").on("click", () => { this.add_item_row({}); this.update_totals(); });
            $("#ai-confirm-btn").on("click", () => this.handle_confirm());
            $("#ai-items-tbody").on("input", ".ai-item-qty, .ai-item-price", () => this.update_totals());
            $("#ai-gov-delivery, #ai-discount-amount").on("change input", () => this.update_totals());
        }

        notes_html() {
            const notes = this.data.notes || {};
            const group = (list, cls) => (list && list.length)
                ? `<ul class="ai-notes-group ${cls}">${list.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : "";
            const body = group(notes.phone, "red") + group(notes.diff, "") + group(notes.ai, "") + group(notes.template, "ai-muted");
            if (!body) return "";
            return `
                <div class="ai-notes-box">
                    <strong>${narjes_icon('warning', {size: 'sm'})} Check before confirming</strong>
                    ${body}
                </div><br/>`;
        }

        // ------------------------------------------------------------ customer card

        phone_source_label(entry) {
            if (this.state.typed) return "typed by you";
            return this.data.phone_source === "free_text" ? "message text" : "📞 field";
        }

        render_customer_card() {
            const st = this.state;
            const res = st.resolution || {};
            const many = st.entries.length > 1;

            const chips = st.entries.map((p) => {
                const on = st.phones.includes(p.e164);
                return `<span class="ai-phone-chip ${on ? "" : "is-off"}">
                    ${many ? `<input type="checkbox" class="ai-phone-toggle" data-e164="${esc(p.e164)}" ${on ? "checked" : ""}/>` : ""}
                    <span>${esc(p.display)}</span>
                    <span class="ai-source">${esc(this.phone_source_label(p))}</span>
                </span>`;
            }).join("");

            const problems = (this.data.phone_problems || []).length
                ? `<div class="ai-banner ai-banner-amber">Could not read as a phone number: <b dir="ltr">${this.data.phone_problems.map(esc).join(", ")}</b></div>`
                : "";

            const free_text_tick = (this.data.phone_source === "free_text" && !st.typed && st.phones.length)
                ? `<label style="display:flex;gap:8px;align-items:center;font-weight:600;">
                        <input type="checkbox" id="ai-phones-confirmed" ${st.phones_confirmed ? "checked" : ""}/>
                        This is the customer's phone (it was not in the order form's 📞 field)
                   </label>` : "";

            const type_phone = `
                <div class="ai-inline-row">
                    <div class="ai-field-group">
                        <label>Customer phone</label>
                        <input type="text" id="ai-typed-phone" dir="ltr" placeholder="07XX XXX XXXX"/>
                    </div>
                    ${st.override_open ? `<div class="ai-field-group">
                        <label>Why the message's phone is wrong <span style="color:var(--red);">*</span></label>
                        <input type="text" id="ai-override-reason" value="${esc(st.override_reason)}"/>
                    </div>` : ""}
                    <button class="btn btn-default btn-sm" id="ai-check-phone">Check</button>
                </div>`;

            let body = "";
            if (res.status === "NO_PHONE" || !st.phones.length) {
                body = `<div class="ai-banner ai-banner-amber"><strong>No phone number.</strong> Type the customer's phone to find or create the customer.
                        ${this.data.phone_section ? `<div class="ai-muted" dir="auto">📞 field: ${esc(this.data.phone_section)}</div>` : ""}</div>${type_phone}`;
            } else if (res.status === "MATCHED") {
                const preview = res.customer_preview || {};
                const owned = new Set(preview.phone_keys || []);
                const extras = st.phones.filter((k) => !owned.has(k));
                const extra_html = (extras.length && preview.free_slot)
                    ? `<label style="display:flex;gap:8px;align-items:center;margin-top:8px;">
                            <input type="checkbox" id="ai-add-extra" ${st.add_extra.length ? "checked" : ""}/>
                            Also save ${esc(st.entries.filter((p) => extras.includes(p.e164)).map((p) => p.display).join(", "))} as this customer's second number
                       </label>` : "";
                body = `<div class="ai-banner ai-banner-green"><strong>Existing customer.</strong> The phone matches exactly.</div>
                        <div class="ai-customer-box">${customer_box(preview, extra_html)}</div>
                        <div class="ai-muted" style="margin-top:6px;">This phone belongs to someone else? Fix the number on
                        <a href="${esc(form_link("Customer", preview.name))}" target="_blank">the customer</a> first, then process the order again.</div>`;
            } else if (res.status === "CONFLICT") {
                body = `<div class="ai-banner ai-banner-red"><strong>These numbers belong to different customers.</strong> Choose the one this order is for. Other customers' numbers are not changed.</div>
                        ${(res.candidates || []).map((c) => `
                            <label class="ai-customer-box ${st.customer === c.name ? "is-chosen" : ""}">
                                <input type="radio" name="ai-pick" value="${esc(c.name)}" ${st.customer === c.name ? "checked" : ""} style="float:inline-end;"/>
                                ${customer_box(c)}
                            </label>`).join("")}`;
            } else if (res.status === "NEW") {
                body = this.new_customer_html();
            }

            const disabled = (res.disabled || []).length
                ? `<div class="ai-banner ai-banner-red">Disabled customer: ${res.disabled.map(esc).join(", ")}. Enable the customer before confirming.</div>` : "";

            const override_link = (this.data.phone_source === "template" && st.entries.length && !st.typed && !st.override_open)
                ? `<div style="margin-top:10px;"><span class="ai-link" id="ai-open-override">The phone in the message is wrong</span></div>` : "";
            const override_box = (st.override_open && res.status !== "NO_PHONE") ? type_phone : "";

            $("#ai-customer-card").html(`
                <h4>${narjes_icon('user', {size: 'md'})} Customer</h4>
                <div class="ai-phone-chips">${chips}</div>
                ${problems}
                ${free_text_tick}
                ${disabled}
                ${body}
                ${override_box}
                ${override_link}
            `);
            this.bind_customer_card();
        }

        new_customer_html() {
            const st = this.state;
            const pre = this.data.prefill || {};
            const phones = st.entries.filter((p) => st.phones.includes(p.e164)).map((p) => p.display).join(", ");
            const old = st.old_customer;
            const can_add = old && old.free_slot;
            return `
                <div class="ai-banner ai-banner-blue"><strong>New customer.</strong> No customer has ${esc(phones)}.</div>
                <div id="ai-new-customer-fields" style="${st.mode === "add_phone_to_existing" ? "display:none;" : ""}">
                    <div class="ai-field-row">
                        <div class="ai-field-group">
                            <label>Customer Name <span style="color:var(--red);">*</span></label>
                            <input type="text" id="ai-new-name" value="${esc(pre.customer_name)}" dir="auto"/>
                        </div>
                        <div class="ai-field-group">
                            <label>Username</label>
                            <input type="text" id="ai-new-username" value="${esc(pre.username)}"/>
                        </div>
                    </div>
                    <div class="ai-field-row">
                        <div class="ai-field-group">
                            <label>Channel</label>
                            <select id="ai-new-channel">${channel_options_html(pre.platform)}</select>
                        </div>
                        <div class="ai-field-group">
                            <label>Governorate</label>
                            <select id="ai-new-gov">${governorate_options_html(pre.governorate)}</select>
                        </div>
                    </div>
                    <div class="ai-field-row">
                        <div class="ai-field-group" style="grid-column: 1 / -1;">
                            <label>Full Address</label>
                            <input type="text" id="ai-new-address" value="${esc(pre.full_address)}" dir="auto"/>
                        </div>
                    </div>
                </div>
                <details id="ai-changed-number" ${st.mode === "add_phone_to_existing" || old ? "open" : ""}>
                    <summary class="ai-link">Existing customer who changed their number?</summary>
                    <div class="ai-muted" style="margin-top:6px;">Find them by their OLD phone number — never by name.</div>
                    <div class="ai-inline-row">
                        <div class="ai-field-group">
                            <label>Their old phone</label>
                            <input type="text" id="ai-old-phone" dir="ltr" value="${esc(st.old_phone)}" placeholder="07XX XXX XXXX"/>
                        </div>
                        <button class="btn btn-default btn-sm" id="ai-find-old">Find</button>
                    </div>
                    ${old ? `<div class="ai-customer-box">${customer_box(old)}</div>
                        ${st.mode === "add_phone_to_existing"
                            ? `<div class="ai-banner ai-banner-green">The order goes to ${esc(old.customer_name)}, and ${esc(phones)} is added to them. <span class="ai-link" id="ai-undo-old">Undo</span></div>`
                            : `<button class="btn btn-default btn-sm" id="ai-use-old" ${can_add ? "" : "disabled"}>Add ${esc(phones)} to ${esc(old.customer_name)} and use them</button>
                               ${can_add ? "" : `<div class="ai-muted">${esc(old.customer_name)} already has two numbers. Change one on the customer first.</div>`}`}` : ""}
                </details>`;
        }

        bind_customer_card() {
            const st = this.state;
            const $card = $("#ai-customer-card");
            $card.find(".ai-phone-toggle").on("change", () => {
                const kept = $card.find(".ai-phone-toggle:checked").map((_, el) => $(el).data("e164")).get();
                if (!kept.length) {
                    frappe.show_alert({ message: "Keep at least one phone number.", indicator: "orange" });
                    this.render_customer_card();
                    return;
                }
                st.phones = kept;
                this.lookup(kept);
            });
            $card.find("#ai-phones-confirmed").on("change", (e) => { st.phones_confirmed = e.target.checked; });
            $card.find("#ai-open-override").on("click", () => { st.override_open = true; this.render_customer_card(); });
            $card.find("#ai-override-reason").on("input", (e) => { st.override_reason = e.target.value; });
            $card.find("#ai-check-phone").on("click", () => {
                const typed = ($("#ai-typed-phone").val() || "").trim();
                if (!typed) return;
                if (st.override_open) st.override_reason = ($("#ai-override-reason").val() || "").trim();
                this.lookup([typed], { typed: true });
            });
            $card.find("input[name=ai-pick]").on("change", (e) => {
                st.customer = e.target.value;
                this.render_customer_card();
            });
            $card.find("#ai-add-extra").on("change", (e) => {
                const preview = (st.resolution || {}).customer_preview || {};
                const owned = new Set(preview.phone_keys || []);
                st.add_extra = e.target.checked ? st.phones.filter((k) => !owned.has(k)) : [];
            });
            $card.find("#ai-find-old").on("click", () => this.find_old_customer());
            $card.find("#ai-use-old").on("click", () => {
                st.mode = "add_phone_to_existing";
                st.customer = st.old_customer.name;
                this.render_customer_card();
            });
            $card.find("#ai-undo-old").on("click", () => {
                st.mode = "new";
                st.customer = null;
                this.render_customer_card();
            });
        }

        find_old_customer() {
            const st = this.state;
            const old = ($("#ai-old-phone").val() || "").trim();
            if (!old) return;
            frappe.call({
                method: "narjes_custom.ai_intake.api.lookup_phones",
                args: { intake_name: this.data.intake_name, phones: JSON.stringify([old]) },
                callback: (r) => {
                    const res = r.message || {};
                    st.old_phone = old;
                    if (!res.ok) {
                        frappe.msgprint({ message: `${esc(old)} is not a valid phone number.`, indicator: "red" });
                        return;
                    }
                    const resolution = res.resolution || {};
                    if (resolution.status !== "MATCHED") {
                        frappe.msgprint({
                            message: resolution.status === "CONFLICT"
                                ? "That old number belongs to more than one customer. Fix the customers first."
                                : "No customer has that number.",
                            indicator: "orange",
                        });
                        st.old_customer = null;
                    } else {
                        st.old_customer = resolution.customer_preview;
                    }
                    this.render_customer_card();
                },
            });
        }

        // The customer the order would go to, or an error message.
        customer_choice() {
            const st = this.state;
            const res = st.resolution || {};
            if (!st.phones.length || res.status === "NO_PHONE") return { error: "Enter the customer's phone number first." };
            if (this.data.phone_source === "free_text" && !st.typed && !st.phones_confirmed) {
                return { error: "Tick “This is the customer's phone” first." };
            }
            if (st.typed && (this.data.phones || []).length && !st.override_reason) {
                return { error: "Say why the phone in the message is wrong." };
            }
            if ((res.disabled || []).length && (res.disabled.includes(st.customer) || res.disabled.includes(res.customer))) {
                return { error: "The customer is disabled. Enable them first." };
            }
            if (st.mode === "matched") return { name: res.customer_preview.customer_name };
            if (st.mode === "pick") {
                if (!st.customer) return { error: "Choose which customer this order is for." };
                const c = (res.candidates || []).find((x) => x.name === st.customer);
                return { name: c ? c.customer_name : st.customer };
            }
            if (st.mode === "add_phone_to_existing") return { name: st.old_customer.customer_name };
            if (st.mode === "new") {
                const name = ($("#ai-new-name").val() || "").trim();
                if (!name) return { error: "Enter the new customer's name." };
                if (st.phones.length > 2) return { error: "A customer can hold two phone numbers. Untick the extra ones." };
                return { name };
            }
            return { error: "Choose the customer first." };
        }

        // ------------------------------------------------------------ items

        catalog_rate(item_code) {
            if (!item_code) return 0;
            const hit = this.item_catalog.find((i) => i.name === item_code);
            return hit ? hit.standard_rate || 0 : 0;
        }

        add_item_row(item = {}) {
            const initialCode = item.item_code_hint || item.item_code || "";
            // Intake doesn't price the order: the AI leaves unit_price at 0 on
            // purpose, so the shop's own price list fills the box. A non-zero
            // value only ever comes from a human editing this row.
            const initialPrice = item.unit_price || item.rate || this.catalog_rate(initialCode);
            const row = $(`
                <tr class="ai-item-row">
                    <td>
                        <div class="ai-autocomplete-wrap">
                            <input type="text" class="ai-item-code" placeholder="Search item..." value="${esc(initialCode)}">
                            <div class="ai-autocomplete-dropdown"></div>
                        </div>
                    </td>
                    <td><input type="text" class="ai-item-desc" value="${esc(item.description || "")}" dir="auto" placeholder="Description…"/></td>
                    <td><input type="number" class="ai-item-qty" value="${esc(item.qty || 1)}" min="1" style="width:100%;"/></td>
                    <td><input type="number" class="ai-item-price" value="${esc(initialPrice)}" min="0"/></td>
                    <td class="ai-item-amount" style="text-align:end;">0</td>
                    <td><input type="text" class="ai-item-notes" value="${esc(item.notes || "")}" placeholder="Notes…" dir="auto"/></td>
                    <td><button class="btn-remove ai-remove-row" title="Remove">${narjes_icon('x', {size: 'xs'})}</button></td>
                </tr>
            `);

            const $input = row.find(".ai-item-code");
            const $dropdown = row.find(".ai-autocomplete-dropdown");

            $input.on("input focus", () => {
                const val = ($input.val() || "").toLowerCase();
                $input.removeClass("has-error");
                const matches = val
                    ? this.item_catalog.filter((i) => i.name.toLowerCase().includes(val) || (i.item_name && i.item_name.toLowerCase().includes(val)))
                    : this.item_catalog;
                const html = matches.slice(0, 20).map((i) =>
                    `<div class="ai-autocomplete-item" data-val="${esc(i.name)}">
                        <div style="font-weight:600;">${esc(i.name)}</div>
                        ${i.item_group ? `<div style="font-size:11px;color:var(--text-muted);">${esc(i.item_group)}</div>` : ""}
                    </div>`).join("");
                $dropdown.html(html || '<div style="padding:8px;font-size:12px;color:var(--text-muted);">No items found</div>').show();
            });

            row.data("code", initialCode);
            $dropdown.on("click", ".ai-autocomplete-item", (e) => {
                const picked = String($(e.currentTarget).data("val"));
                $input.val(picked);
                $dropdown.hide();
                // Follow the newly picked item's list price, but never overwrite
                // a price the reviewer typed themselves.
                const $price = row.find(".ai-item-price");
                const current = parseFloat($price.val()) || 0;
                if (!current || current === this.catalog_rate(row.data("code"))) {
                    $price.val(this.catalog_rate(picked));
                }
                row.data("code", picked);
                this.update_totals();
            });

            $("#ai-items-tbody").append(row);
            row.find(".ai-remove-row").on("click", () => {
                row.remove();
                this.update_totals();
            });
        }

        items_total() {
            let total = 0;
            $("#ai-items-tbody .ai-item-row").each(function () {
                const qty = parseFloat($(this).find(".ai-item-qty").val()) || 0;
                const price = parseFloat($(this).find(".ai-item-price").val()) || 0;
                $(this).find(".ai-item-amount").text(money(qty * price));
                total += qty * price;
            });
            return total;
        }

        update_totals() {
            const items = this.items_total();
            $("#ai-grand-total").text(money(items));
            this.render_amounts(items);
        }

        // The order form's own money lines next to what this order adds up to.
        // Information only: prices are the shop's decision.
        render_amounts(items_total) {
            const msg = (this.data && this.data.amounts) || {};
            const discount = parseFloat($("#ai-discount-amount").val()) || 0;
            const fee = delivery_fee($("#ai-gov-delivery").val());
            const total = items_total - discount + fee;
            const line = (label, expected, actual) => {
                if (expected === undefined || expected === null) return "";
                const same = Math.round(expected) === Math.round(actual);
                return `<div>${esc(label)}: message ${money(expected)} · this order ${money(actual)}
                    <span class="${same ? "ok" : "warn"}">${same ? "✓" : "⚠ differs by " + money(actual - expected)}</span></div>`;
            };
            const html = line("Order amount", msg.order, items_total - discount) + line("Delivery", msg.fee, fee) + line("Total", msg.total, total);
            const assumed = (msg.assumed_thousands || []).length ? `<div class="ai-muted">Read as thousands: ${msg.assumed_thousands.map(esc).join(", ")}</div>` : "";
            $("#ai-amounts").html(html ? html + assumed : `<span class="ai-muted">The message has no amounts to compare.</span>`);
        }

        validate_and_get_missing_items() {
            const catalogNames = new Set(this.item_catalog.map((i) => i.name));
            const missing = [];
            let isValid = true;
            $("#ai-items-tbody .ai-item-row").each((idx, row) => {
                const $input = $(row).find(".ai-item-code");
                const code = ($input.val() || "").trim();
                const qty = parseFloat($(row).find(".ai-item-qty").val()) || 0;
                if (!code || qty <= 0) {
                    $input.addClass("has-error");
                    isValid = false;
                } else if (!catalogNames.has(code)) {
                    $input.addClass("has-error");
                    missing.push({ code, input: $input });
                    isValid = false;
                }
            });
            return { isValid, missing };
        }

        show_missing_item_dialog(missingItems) {
            const item = missingItems[0];
            const badCode = item.code;
            const suggestions = this.item_catalog
                .map((i) => ({ item: i, score: levenshtein(badCode.toLowerCase(), i.name.toLowerCase()) }))
                .sort((a, b) => a.score - b.score)
                .slice(0, 3)
                .map((s) => s.item);
            const d = new frappe.ui.Dialog({
                title: "Item Not Found",
                fields: [{
                    fieldtype: "HTML",
                    fieldname: "info",
                    options: `
                        <p>The item code <strong>"${esc(badCode)}"</strong> does not exist.</p>
                        <h5 style="margin-top:16px;">Suggested items:</h5>
                        <div>${suggestions.map((s) =>
                            `<button class="btn btn-default btn-sm ai-suggest-btn" data-val="${esc(s.name)}" style="margin:4px;">
                                <strong>${esc(s.name)}</strong> <span class="ai-muted">${esc(s.item_group || "")}</span>
                            </button>`).join("")}</div>
                        <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--border-color);">
                            <a href="${esc(form_link("Item", "new"))}?item_name=${encodeURIComponent(badCode)}" target="_blank" class="btn btn-primary btn-sm">+ Create New Item</a>
                            <p class="ai-muted" style="margin-top:6px;">Opens in a new tab. Save the item, then confirm again.</p>
                        </div>`,
                }],
                primary_action_label: "Close",
                primary_action: () => d.hide(),
            });
            d.show();
            d.$wrapper.find(".ai-suggest-btn").on("click", function () {
                item.input.val(String($(this).data("val"))).removeClass("has-error");
                d.hide();
            });
        }

        // ------------------------------------------------------------ confirm / discard

        handle_confirm() {
            const st = this.state;
            const choice = this.customer_choice();
            if (choice.error) {
                frappe.msgprint({ message: esc(choice.error), indicator: "orange" });
                return;
            }
            const validation = this.validate_and_get_missing_items();
            if (!validation.isValid) {
                if (validation.missing.length) this.show_missing_item_dialog(validation.missing);
                else frappe.msgprint({ message: "Please fill in all item rows correctly.", indicator: "red" });
                return;
            }

            const order_items = [];
            $("#ai-items-tbody .ai-item-row").each(function () {
                const item_code = ($(this).find(".ai-item-code").val() || "").trim();
                order_items.push({
                    item_code,
                    item_name: item_code,
                    description: ($(this).find(".ai-item-desc").val() || "").trim() || item_code,
                    qty: parseFloat($(this).find(".ai-item-qty").val()) || 1,
                    rate: parseFloat($(this).find(".ai-item-price").val()) || 0,
                    notes: ($(this).find(".ai-item-notes").val() || "").trim(),
                });
            });

            const reviewed = {
                resolution_token: st.resolution.token,
                customer_mode: st.mode,
                customer: st.mode === "matched" ? st.resolution.customer : st.customer,
                phones: st.phones,
                phones_confirmed: st.phones_confirmed,
                override_reason: st.override_reason,
                old_phone: st.mode === "add_phone_to_existing" ? st.old_phone : "",
                add_phones_to_customer: st.mode === "matched" ? st.add_extra : [],
                new_customer: st.mode === "new" ? {
                    customer_name: ($("#ai-new-name").val() || "").trim(),
                    username: ($("#ai-new-username").val() || "").trim(),
                    platform: $("#ai-new-channel").val() || "",
                    governorate: $("#ai-new-gov").val() || "",
                    full_address: ($("#ai-new-address").val() || "").trim(),
                } : null,
                order: {
                    delivery_date: $("#ai-delivery-date").val() || frappe.datetime.get_today(),
                    currency: $("#ai-currency").val() || "IQD",
                    gift: $("#ai-gift").is(":checked"),
                    priority: $("#ai-priority").val() || null,
                    governorate_of_delivery: $("#ai-gov-delivery").val() || "",
                    discount_amount: parseFloat($("#ai-discount-amount").val()) || 0,
                    custom_details: ($("#ai-custom-details").val() || "").trim(),
                    order_items,
                },
            };

            const phones = st.entries.filter((p) => st.phones.includes(p.e164)).map((p) => p.display).join(", ");
            frappe.confirm(`Create the order for <b>${esc(choice.name)}</b> (<span dir="ltr">${esc(phones)}</span>)?`, () => {
                frappe.dom.freeze("Creating the order…");
                frappe.call({
                    method: "narjes_custom.ai_intake.api.confirm_intake",
                    args: { intake_name: this.data.intake_name, reviewed_data: JSON.stringify(reviewed) },
                    callback: (r) => {
                        frappe.dom.unfreeze();
                        const res = r.message || {};
                        if (res.ok) return this.render_success_screen(res);
                        if (res.reason === "resolution_changed") {
                            st.resolution = res.resolution;
                            this.reset_mode();
                            this.render_customer_card();
                            frappe.msgprint({
                                title: "Customers changed",
                                message: "Someone changed the customers for this phone since you opened the order. Check the customer again, then confirm.",
                                indicator: "orange",
                            });
                            return;
                        }
                        if (res.reason === "already_confirmed") {
                            frappe.msgprint({
                                message: `This intake was already confirmed: <a href="${esc(form_link("Sales Order", res.sales_order))}" target="_blank">${esc(res.sales_order)}</a>.`,
                                indicator: "orange",
                            });
                        }
                    },
                    error: () => frappe.dom.unfreeze(),
                });
            });
        }

        handle_discard() {
            frappe.prompt(
                { fieldname: "reason", fieldtype: "Small Text", label: "Why is this intake being discarded?", reqd: 1 },
                (values) => {
                    frappe.call({
                        method: "narjes_custom.ai_intake.api.discard_intake",
                        args: { intake_name: this.data.intake_name, reason: values.reason },
                        callback: (r) => {
                            if (r.exc) return;
                            frappe.show_alert({ message: "Intake discarded", indicator: "gray" });
                            this.render_intake_screen();
                        },
                    });
                },
                "Discard intake",
                "Discard"
            );
        }

        // ------------------------------------------------------------ other screens

        render_success_screen(result) {
            this.$main.html(`
                <div class="ai-intake-wrap">
                    <div class="ai-intake-card" style="text-align:center;border-color:var(--narjes-sage);background:var(--narjes-fern-tint);">
                        <h3 style="color:var(--narjes-fern-strong);margin-bottom:12px;">${narjes_icon('confetti', {size: 'md'})} Order Created</h3>
                        <p style="color:var(--narjes-fern-strong);">
                            ${result.created_new_customer ? "A new customer was created and a" : "A"} Sales Order has been created.
                            ${(result.added_phones || []).length ? `<br/>Added ${result.added_phones.map(esc).join(", ")} to the customer.` : ""}
                        </p>
                        <div style="display:flex;gap:12px;justify-content:center;margin-top:20px;flex-wrap:wrap;">
                            <a href="${esc(form_link("Sales Order", result.sales_order))}" target="_blank" class="btn btn-primary">
                                ${narjes_icon('file-text', {size: 'xs'})} Sales Order ${esc(result.sales_order)}
                            </a>
                            <a href="${esc(form_link("Customer", result.customer))}" target="_blank" class="btn btn-default">
                                ${narjes_icon('user', {size: 'xs'})} Customer ${esc(result.customer)}
                            </a>
                        </div>
                    </div>
                    <button class="btn btn-default" id="ai-new-intake-btn" style="margin-top:10px;">${narjes_icon('plus-circle', {size: 'xs'})} Process another order</button>
                </div>
            `);
            $("#ai-new-intake-btn").on("click", () => this.render_intake_screen());
        }

        show_spinner(label) {
            const started = Date.now();
            this.$main.html(`
                <div class="ai-intake-wrap">
                    <div class="ai-intake-card ai-spinner-wrap">
                        <div class="spinner-border text-primary" role="status" style="width:30px;height:30px;border-width:3px;"></div>
                        <div class="ai-loading-step active">${esc(label)} <span id="ai-elapsed">0s</span></div>
                    </div>
                </div>
            `);
            this.spinnerInterval = setInterval(() => {
                $("#ai-elapsed").text(Math.round((Date.now() - started) / 1000) + "s");
            }, 500);
        }

        clear_spinner_interval() {
            if (this.spinnerInterval) {
                clearInterval(this.spinnerInterval);
                this.spinnerInterval = null;
            }
        }

        show_error(msg) {
            this.clear_spinner_interval();
            this.$main.html(`
                <div class="ai-intake-wrap">
                    <div class="ai-intake-card" style="border-color:var(--red);">
                        <h4>${narjes_icon('x-circle', {size: 'md'})} Error</h4>
                        <pre style="white-space:pre-wrap;font-size:13px;color:var(--red);background:#fef2f2;padding:12px;border-radius:4px;">${esc(msg)}</pre>
                        <button class="btn btn-default" id="ai-retry-btn" style="margin-top:14px;">${narjes_icon('arrow-left', {size: 'xs'})} Back to intake</button>
                    </div>
                </div>
            `);
            $("#ai-retry-btn").on("click", () => this.render_intake_screen());
        }

        show_duplicate_warning(data) {
            this.$main.html(`
                <div class="ai-intake-wrap">
                    <div class="ai-intake-card" style="border-color:#f59e0b;background:#fffbeb;">
                        <h4 style="color:#d97706;">${narjes_icon('warning', {size: 'md'})} Already Processed</h4>
                        <p style="color:#92400e;font-size:14px;margin-bottom:20px;">${esc(data.message)}</p>
                        <a href="${esc(form_link("Sales Order", data.created_sales_order))}" target="_blank" class="btn btn-primary">
                            Open Sales Order ${esc(data.created_sales_order)}
                        </a>
                        <button class="btn btn-default" id="ai-force-new-btn" style="margin-inline-start:8px;">Process as a NEW order anyway</button>
                        <br/><br/>
                        <button class="btn btn-default" id="ai-back-dup-btn">${narjes_icon('arrow-left', {size: 'xs'})} Process a different order</button>
                    </div>
                </div>
            `);
            $("#ai-back-dup-btn").on("click", () => this.render_intake_screen());
            $("#ai-force-new-btn").on("click", () => {
                frappe.confirm("This text already made an order. Create a second, separate order from it?", () =>
                    this.handle_process(1, this.last_text));
            });
        }

        show_extraction_failed(data) {
            this.$main.html(`
                <div class="ai-intake-wrap">
                    <div class="ai-intake-card" style="border-color:var(--red);">
                        <h4>${narjes_icon('x-circle', {size: 'md'})} Extraction Failed</h4>
                        <p style="color:var(--red);font-size:13px;background:#fef2f2;padding:12px;border-radius:4px;">${esc(data.error_message || "Unknown error")}</p>
                        <p style="font-size:13px;color:var(--text-muted);margin-top:14px;">
                            Saved as <a href="${esc(form_link("AI Order Intake", data.intake_name))}" target="_blank">${esc(data.intake_name)}</a> (Failed).
                            Try again, or enter the order manually.
                        </p>
                        <button class="btn btn-primary" id="ai-retry-fail-btn" style="margin-top:14px;">Try again</button>
                        <button class="btn btn-default" id="ai-back-fail-btn" style="margin-top:14px;">${narjes_icon('arrow-left', {size: 'xs'})} Back to intake</button>
                    </div>
                </div>
            `);
            $("#ai-retry-fail-btn").on("click", () => this.handle_process(0, this.last_text));
            $("#ai-back-fail-btn").on("click", () => this.render_intake_screen());
        }
    }

    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "AI Order Intake",
        single_column: true,
    });

    const style = document.createElement("style");
    style.textContent = AI_INTAKE_CSS;
    document.head.appendChild(style);

    const app = new AIOrderIntakePage(page, wrapper);
    wrapper.ai_intake_app = app;
};
