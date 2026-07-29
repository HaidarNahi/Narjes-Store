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
        background: linear-gradient(135deg, var(--primary), var(--blue-600));
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
    .ai-match-phone { background: #d1fae5; color: #065f46; }
    .ai-match-fuzzy { background: #fef3c7; color: #92400e; }
    .ai-match-none { background: #f3f4f6; color: #6b7280; }
    .ai-status-Draft { background: #f3f4f6; color: #374151; }
    .ai-status-Review { background: #e0e7ff; color: #3730a3; }
    
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
    `;

    // Iraq's 18 governorates — must stay in sync with
    // narjes_custom.business_logic.IRAQ_GOVERNORATES (the canonical list
    // used server-side for Customer.governorate / Sales Order.
    // governorate_of_delivery, both proper Select fields — see
    // NARJES_STORE_SYSTEM.md §14.6). A free-text input here would let a
    // human reviewer type a value the backend Select field then rejects.
    const IRAQ_GOVERNORATES = [
        "بغداد", "بابل", "واسط", "ديالى", "الديوانية", "كربلاء", "النجف",
        "ذي قار", "ميسان", "المثنى", "البصرة", "الانبار", "صلاح الدين",
        "كركوك", "نينوى", "اربيل", "سليمانية", "دهوك",
    ];

    function governorate_options_html(selected) {
        let html = `<option value="" ${!selected ? "selected" : ""}>— None —</option>`;
        IRAQ_GOVERNORATES.forEach((gov) => {
            html += `<option value="${gov}" ${selected === gov ? "selected" : ""}>${gov}</option>`;
        });
        return html;
    }

    // Simple Levenshtein distance for fuzzy matching
    function levenshtein(a, b) {
        if (a.length === 0) return b.length;
        if (b.length === 0) return a.length;
        const matrix = [];
        for (let i = 0; i <= b.length; i++) { matrix[i] = [i]; }
        for (let j = 0; j <= a.length; j++) { matrix[0][j] = j; }
        for (let i = 1; i <= b.length; i++) {
            for (let j = 1; j <= a.length; j++) {
                if (b.charAt(i - 1) === a.charAt(j - 1)) {
                    matrix[i][j] = matrix[i - 1][j - 1];
                } else {
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j - 1] + 1,
                        matrix[i][j - 1] + 1,
                        matrix[i - 1][j] + 1
                    );
                }
            }
        }
        return matrix[b.length][a.length];
    }

    class AIOrderIntakePage {
        constructor(page, wrapper) {
            this.page = page;
            this.wrapper = wrapper;
            this.intake_data = null;
            this.item_catalog = []; // Populated from API response
            this.render_intake_screen();
        }

        render_intake_screen() {
            const $main = $(this.wrapper).find(".layout-main-section");
            $main.html(`
                <div class="ai-intake-wrap">
                    <div class="ai-intake-card">
                        <h4><span style="font-size:18px">📋</span> Paste Order Text</h4>
                        <p style="font-size:13px;color:var(--text-muted);margin-bottom:12px;">
                            Paste the customer's WhatsApp message or any informal order text below.
                            Arabic, English, or mixed — all formats work.
                        </p>
                        <textarea
                            class="ai-intake-textarea"
                            id="ai-raw-text"
                            placeholder="مثال: احمد / 07701234567 / MDF 30*40 قطعتين / التوصيل الخميس..."
                            dir="auto"
                        ></textarea>
                        <br/>
                        <button class="btn ai-btn-gradient ai-intake-btn-process" id="ai-process-btn">
                            ✨ Extract & Match
                        </button>
                        <button class="btn btn-default" id="ai-clear-btn" style="margin-top:14px;margin-right:10px;">
                            Clear
                        </button>
                    </div>
                </div>
            `);

            $("#ai-process-btn").on("click", () => this.handle_process());
            $("#ai-clear-btn").on("click", () => $("#ai-raw-text").val("").focus());
        }

        handle_process() {
            const raw_text = $("#ai-raw-text").val().trim();
            if (!raw_text) {
                frappe.msgprint({ message: "Please paste some order text first.", indicator: "orange" });
                return;
            }

            this.show_spinner(["Analyzing text...", "Matching items...", "Finding customer..."]);

            frappe.call({
                method: "narjes_custom.ai_intake.api.process_intake",
                args: { raw_text },
                callback: (r) => {
                    this.clear_spinner_interval();
                    if (r.exc) { this.show_error(r.exc); return; }
                    const data = r.message;

                    if (data.duplicate) {
                        this.show_duplicate_warning(data);
                        return;
                    }
                    if (data.status === "Failed") {
                        this.show_extraction_failed(data);
                        return;
                    }

                    this.intake_data = data;
                    this.item_catalog = data.item_catalog || [];
                    this.render_review_screen(data);
                },
                error: (err) => {
                    this.clear_spinner_interval();
                    this.show_error(String(err));
                },
            });
        }

        render_review_screen(data) {
            const ex = data.extracted || {};
            const match = data.match || {};
            const items = ex.order_items || [];
            const notes = ex.extraction_notes || [];

            const matchBadgeClass = {
                "Phone": "ai-match-phone",
                "Fuzzy Name": "ai-match-fuzzy",
                "None": "ai-match-none",
            }[match.method] || "ai-match-none";

            const matchBadgeText = {
                "Phone": `📞 Phone match (${match.confidence}%)`,
                "Fuzzy Name": `🔤 Name match (${match.confidence}%)`,
                "None": "➕ No match — new customer will be created",
            }[match.method] || "No match";

            const statusClass = "ai-status-" + (data.status === "Needs Review" ? "Review" : "Draft");

            const $main = $(this.wrapper).find(".layout-main-section");
            $main.html(`
                <div class="ai-intake-wrap">
                    <div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;justify-content:space-between;">
                        <div style="display:flex;align-items:center;gap:12px;">
                            <button class="btn btn-default btn-sm" id="ai-back-btn">← Back</button>
                            <h3 style="margin:0;font-size:16px;">Review Extracted Order</h3>
                            <span class="ai-status-pill ${statusClass}">${data.status}</span>
                        </div>
                        <span style="font-size:12px;color:var(--text-muted);">ID: ${data.intake_name}</span>
                    </div>

                    ${notes.length ? `
                    <div class="ai-notes-box">
                        <div style="display:flex;justify-content:space-between;cursor:pointer;" id="ai-toggle-notes">
                            <strong>⚠️ AI Extraction Notes (review these)</strong>
                            <span id="ai-notes-icon">▼</span>
                        </div>
                        <ul id="ai-notes-list">${notes.map(n => `<li>${frappe.utils.escape_html(n)}</li>`).join("")}</ul>
                    </div><br/>` : ""}

                    <!-- Customer Section -->
                    <div class="ai-intake-card">
                        <h4><span style="font-size:16px">👤</span> Customer Details</h4>
                        <div class="ai-field-row" style="align-items:center;">
                            <div>
                                <span class="ai-match-badge ${matchBadgeClass}">${matchBadgeText}</span>
                            </div>
                            <div class="ai-field-group">
                                <label>Action</label>
                                <select id="ai-customer-choice">
                                    ${match.customer ? `<option value="existing">Use existing: ${match.customer}</option>` : ""}
                                    <option value="new" ${!match.customer ? "selected" : ""}>Create new customer</option>
                                    ${match.customer ? `<option value="search">Search for different customer…</option>` : ""}
                                </select>
                            </div>
                        </div>

                        <!-- Existing customer search (hidden by default) -->
                        <div id="ai-search-customer-wrap" style="display:none;margin-top:10px;">
                            <div class="ai-field-group">
                                <label>Search Customer</label>
                                <input type="text" id="ai-customer-search" placeholder="Type customer name…"/>
                            </div>
                            <div id="ai-customer-search-results" style="margin-top:6px;"></div>
                        </div>

                        <!-- New customer fields -->
                        <div id="ai-new-customer-fields" style="margin-top:14px;${match.customer ? 'display:none;' : ''}">
                            <div class="ai-field-row">
                                <div class="ai-field-group">
                                    <label>Customer Name <span style="color:var(--red);">*</span></label>
                                    <input type="text" id="ai-new-name" value="${frappe.utils.escape_html(ex.customer_name || "")}" dir="auto"/>
                                    <div class="ai-error-msg">Name is required</div>
                                </div>
                                <div class="ai-field-group">
                                    <label>Main Phone</label>
                                    <input type="text" id="ai-new-phone" value="${frappe.utils.escape_html((ex.phone_numbers || [])[0] || "")}"/>
                                </div>
                            </div>
                            <div class="ai-field-row">
                                <div class="ai-field-group">
                                    <label>Secondary Phone</label>
                                    <input type="text" id="ai-new-phone2" value="${frappe.utils.escape_html((ex.phone_numbers || [])[1] || "")}"/>
                                </div>
                                <div class="ai-field-group">
                                    <label>Username</label>
                                    <input type="text" id="ai-new-username" value="${frappe.utils.escape_html(ex.username || "")}"/>
                                </div>
                            </div>
                            <div class="ai-field-row">
                                <div class="ai-field-group">
                                    <label>Governorate</label>
                                    <select id="ai-new-gov">${governorate_options_html(ex.governorate)}</select>
                                </div>
                                <div class="ai-field-group">
                                    <label>Full Address</label>
                                    <input type="text" id="ai-new-address" value="${frappe.utils.escape_html(ex.address || "")}"/>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Order Details -->
                    <div class="ai-intake-card">
                        <h4><span style="font-size:16px">📦</span> Order Information</h4>
                        <div class="ai-field-row">
                            <div class="ai-field-group">
                                <label>Delivery Date</label>
                                <input type="date" id="ai-delivery-date" value="${ex.delivery_date || ""}"/>
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
                                    <option value="High" ${ex.priority === "High" ? "selected" : ""}>High</option>
                                    <option value="Medium" ${ex.priority === "Medium" ? "selected" : ""}>Medium</option>
                                    <option value="Low" ${ex.priority === "Low" ? "selected" : ""}>Low</option>
                                </select>
                            </div>
                            <div class="ai-field-group">
                                <label>Governorate of Delivery</label>
                                <select id="ai-gov-delivery">${governorate_options_html(ex.governorate)}</select>
                            </div>
                        </div>
                        <div class="ai-field-row">
                            <div class="ai-field-group">
                                <label>Discount Amount</label>
                                <input type="number" id="ai-discount-amount" value="${ex.discount_amount || 0}" min="0"/>
                            </div>
                            <div class="ai-field-group">
                                <label>Custom Details</label>
                                <input type="text" id="ai-custom-details" value="${frappe.utils.escape_html(ex.custom_details || "")}" placeholder="Any extra unstructured details..."/>
                            </div>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;margin-top:4px;">
                            <input type="checkbox" id="ai-gift" ${ex.gift ? "checked" : ""}/>
                            <label for="ai-gift" style="font-size:14px;cursor:pointer;font-weight:600;">🎁 Mark as Gift Order</label>
                        </div>
                    </div>

                    <!-- Items Table -->
                    <div class="ai-intake-card">
                        <h4><span style="font-size:16px">🛍️</span> Items</h4>
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
                            <tbody id="ai-items-tbody">
                            </tbody>
                            <tfoot>
                                <tr class="ai-total-row">
                                    <td colspan="4" style="text-align:right;">Total:</td>
                                    <td id="ai-grand-total">0.00</td>
                                    <td colspan="2"></td>
                                </tr>
                            </tfoot>
                        </table>
                        <button class="btn btn-default btn-xs" id="ai-add-item-btn" style="margin-top:12px;">+ Add row</button>
                    </div>

                    <!-- Confirm -->
                    <div style="display:flex;gap:12px;margin-top:4px;margin-bottom:40px;">
                        <button class="btn ai-btn-gradient btn-lg" id="ai-confirm-btn">
                            ✅ Confirm &amp; Create Order
                        </button>
                        <button class="btn btn-default btn-lg" id="ai-cancel-btn">Cancel</button>
                    </div>
                </div>
            `);

            // Initialize items
            (items.length ? items : [{}]).forEach(item => this.add_item_row(item));
            this.update_totals();

            // Notes toggle
            $("#ai-toggle-notes").on("click", function() {
                $("#ai-notes-list").slideToggle(200);
                const icon = $("#ai-notes-icon");
                icon.text(icon.text() === "▼" ? "▲" : "▼");
            });

            // Event handlers
            $("#ai-back-btn, #ai-cancel-btn").on("click", () => this.render_intake_screen());
            $("#ai-add-item-btn").on("click", () => { this.add_item_row({}); this.update_totals(); });
            $("#ai-confirm-btn").on("click", () => this.handle_confirm());
            
            // Recalculate totals when qty/price changes
            $("#ai-items-tbody").on("input", ".ai-item-qty, .ai-item-price", () => this.update_totals());

            // Customer choice toggle
            $("#ai-customer-choice").on("change", function () {
                const val = $(this).val();
                $("#ai-new-customer-fields").toggle(val === "new");
                $("#ai-search-customer-wrap").toggle(val === "search");
            });

            // Customer live search
            let search_timer;
            $("#ai-customer-search").on("input", function () {
                clearTimeout(search_timer);
                const q = $(this).val().trim();
                if (!q) { $("#ai-customer-search-results").html(""); return; }
                search_timer = setTimeout(() => {
                    frappe.call({
                        method: "narjes_custom.ai_intake.api.get_customers_for_search",
                        args: { query: q },
                        callback: (r) => {
                            const list = (r.message || []).map(c =>
                                `<div class="ai-search-result" data-name="${c.name}" style="padding:6px 10px;cursor:pointer;border-bottom:1px solid var(--border-color);font-size:13px;">
                                    ${frappe.utils.escape_html(c.customer_name)}
                                    ${c.main_phone_number ? `<span style="color:var(--text-muted);margin-left:8px;">${c.main_phone_number}</span>` : ""}
                                 </div>`
                            ).join("");
                            $("#ai-customer-search-results").html(
                                list
                                    ? `<div style="border:1px solid var(--border-color);border-radius:4px;background:var(--card-bg);">${list}</div>`
                                    : `<span style="font-size:12px;color:var(--text-muted);">No customers found.</span>`
                            );

                            $(".ai-search-result").on("click", function () {
                                const name = $(this).data("name");
                                $("#ai-customer-choice").val("search");
                                $("#ai-customer-choice").append(
                                    `<option value="found:${name}" selected>Selected: ${name}</option>`
                                ).val(`found:${name}`);
                                $("#ai-customer-search-results").html(
                                    `<div style="font-size:13px;padding:4px 0;color:var(--primary);">✓ Selected: <strong>${name}</strong></div>`
                                );
                            });
                        },
                    });
                }, 300);
            });
        }

        update_totals() {
            let grandTotal = 0;
            $("#ai-items-tbody .ai-item-row").each(function () {
                const qty = parseFloat($(this).find(".ai-item-qty").val()) || 0;
                const price = parseFloat($(this).find(".ai-item-price").val()) || 0;
                const amount = qty * price;
                $(this).find(".ai-item-amount").text(amount.toFixed(2));
                grandTotal += amount;
            });
            $("#ai-grand-total").text(grandTotal.toFixed(2));
        }

        add_item_row(item = {}) {
            const initialCode = item.item_code_hint || item.item_code || "";
            const row = $(`
                <tr class="ai-item-row">
                    <td>
                        <div class="ai-autocomplete-wrap">
                            <input type="text" class="ai-item-code" placeholder="Search item..." value="${frappe.utils.escape_html(initialCode)}">
                            <div class="ai-autocomplete-dropdown"></div>
                        </div>
                    </td>
                    <td><input type="text" class="ai-item-desc" value="${frappe.utils.escape_html(item.description || "")}" dir="auto" placeholder="Description…"/></td>
                    <td><input type="number" class="ai-item-qty" value="${item.qty || 1}" min="1" style="width:100%;"/></td>
                    <td><input type="number" class="ai-item-price" value="${item.unit_price || item.rate || 0}" min="0"/></td>
                    <td class="ai-item-amount" style="text-align:right;">0.00</td>
                    <td><input type="text" class="ai-item-notes" value="${frappe.utils.escape_html(item.notes || "")}" placeholder="Notes…" dir="auto"/></td>
                    <td><button class="btn-remove ai-remove-row" title="Remove">×</button></td>
                </tr>
            `);

            const $input = row.find('.ai-item-code');
            const $dropdown = row.find('.ai-autocomplete-dropdown');

            // Autocomplete logic
            $input.on('input focus', () => {
                const val = $input.val().toLowerCase();
                $input.removeClass('has-error');
                let matches = this.item_catalog;
                
                if (val) {
                    matches = this.item_catalog.filter(i => 
                        i.name.toLowerCase().includes(val) || 
                        (i.item_name && i.item_name.toLowerCase().includes(val))
                    );
                }
                
                // Show top 20 matches
                const html = matches.slice(0, 20).map(i => 
                    `<div class="ai-autocomplete-item" data-val="${frappe.utils.escape_html(i.name)}">
                        <div style="font-weight:600;">${frappe.utils.escape_html(i.name)}</div>
                        ${i.item_group ? `<div style="font-size:11px;color:var(--text-muted);">${frappe.utils.escape_html(i.item_group)}</div>` : ''}
                    </div>`
                ).join("");
                
                if (html) {
                    $dropdown.html(html).show();
                } else {
                    $dropdown.html('<div style="padding:8px;font-size:12px;color:var(--text-muted);">No items found</div>').show();
                }
            });

            $dropdown.on('click', '.ai-autocomplete-item', function() {
                $input.val($(this).data('val'));
                $dropdown.hide();
            });

            // Close dropdown when clicking outside
            $(document).on('click', function(e) {
                if (!$(e.target).closest('.ai-autocomplete-wrap').length) {
                    $dropdown.hide();
                }
            });

            $("#ai-items-tbody").append(row);

            row.find('.ai-remove-row').on('click', () => {
                row.remove();
                this.update_totals();
            });
        }

        validate_and_get_missing_items() {
            const catalogNames = new Set(this.item_catalog.map(i => i.name));
            const missing = [];
            let isValid = true;
            
            $("#ai-items-tbody .ai-item-row").each((idx, row) => {
                const $input = $(row).find(".ai-item-code");
                const code = $input.val().trim();
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

        show_missing_item_dialog(missingItems, continueCallback) {
            // Take the first missing item to show in the dialog
            const item = missingItems[0];
            const badCode = item.code;
            
            // Suggest alternatives
            const suggestions = this.item_catalog
                .map(i => ({ item: i, score: levenshtein(badCode.toLowerCase(), i.name.toLowerCase()) }))
                .sort((a, b) => a.score - b.score)
                .slice(0, 3)
                .map(s => s.item);

            const suggestionHtml = suggestions.map(s => 
                `<button class="btn btn-default btn-sm ai-suggest-btn" data-val="${frappe.utils.escape_html(s.name)}" style="margin:4px;display:inline-flex;flex-direction:column;align-items:flex-start;">
                    <strong>${frappe.utils.escape_html(s.name)}</strong>
                    <span style="font-size:10px;color:var(--text-muted);">${frappe.utils.escape_html(s.item_group || '')}</span>
                </button>`
            ).join('');

            const d = new frappe.ui.Dialog({
                title: '⚠️ Item Not Found',
                fields: [
                    {
                        fieldtype: 'HTML',
                        fieldname: 'info',
                        options: `
                            <p>The item code <strong>"${frappe.utils.escape_html(badCode)}"</strong> does not exist in the system.</p>
                            <p style="color:var(--text-muted);font-size:13px;">Please select an alternative or create a new item.</p>
                            <div style="margin-top:16px;">
                                <h5>Suggested Alternatives:</h5>
                                <div>${suggestionHtml}</div>
                            </div>
                            <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--border-color);">
                                <a href="/app/item/new?item_name=${encodeURIComponent(badCode)}" target="_blank" class="btn btn-primary btn-sm">
                                    + Create New Item
                                </a>
                                <p style="font-size:12px;color:var(--text-muted);margin-top:6px;">(Opens in a new tab. Save the item, then try confirming again.)</p>
                            </div>
                        `
                    }
                ],
                primary_action_label: 'Close',
                primary_action: () => d.hide()
            });

            d.show();

            // Bind suggestion click
            d.$wrapper.find('.ai-suggest-btn').on('click', function() {
                const val = $(this).data('val');
                item.input.val(val).removeClass('has-error');
                d.hide();
                // If there are more missing items, re-validate
                continueCallback();
            });
        }

        handle_confirm() {
            // Customer Validation
            const choice = $("#ai-customer-choice").val();
            let customer_name, customer_choice;

            if (choice === "existing" && this.intake_data.match.customer) {
                customer_name = this.intake_data.match.customer;
                customer_choice = "existing";
            } else if (choice && choice.startsWith("found:")) {
                customer_name = choice.replace("found:", "");
                customer_choice = "existing";
            } else if (choice === "new") {
                customer_name = $("#ai-new-name").val().trim();
                customer_choice = "new";
                
                if (!customer_name) {
                    $("#ai-new-name").addClass("has-error").next('.ai-error-msg').show();
                    return;
                } else {
                    $("#ai-new-name").removeClass("has-error").next('.ai-error-msg').hide();
                }
            } else {
                frappe.msgprint({ message: "Please select a customer option.", indicator: "orange" });
                return;
            }

            // Item Validation
            const validation = this.validate_and_get_missing_items();
            
            if (!validation.isValid) {
                if (validation.missing.length > 0) {
                    // Show dialog for the first missing item
                    this.show_missing_item_dialog(validation.missing, () => {
                        // Called when a user clicks a suggestion, can re-trigger validation manually later.
                    });
                } else {
                    frappe.msgprint({ message: "Please fill in all item rows correctly.", indicator: "red" });
                }
                return;
            }

            // Collect items
            const order_items = [];
            $("#ai-items-tbody .ai-item-row").each(function () {
                const item_code = $(this).find(".ai-item-code").val().trim();
                order_items.push({
                    item_code: item_code,
                    item_name: item_code,
                    description: $(this).find(".ai-item-desc").val().trim() || item_code,
                    qty: parseFloat($(this).find(".ai-item-qty").val()) || 1,
                    rate: parseFloat($(this).find(".ai-item-price").val()) || 0,
                    notes: $(this).find(".ai-item-notes").val().trim(),
                });
            });

            if (!order_items.length) {
                frappe.msgprint({ message: "Order must have at least one item.", indicator: "red" });
                return;
            }

            const reviewed_data = {
                customer_choice,
                customer_name,
                main_phone_number: $("#ai-new-phone").val().trim(),
                secondary_phone_number: $("#ai-new-phone2").val().trim(),
                username: $("#ai-new-username").val().trim(),
                governorate: $("#ai-new-gov").val().trim(),
                full_address: $("#ai-new-address").val().trim(),
                delivery_date: $("#ai-delivery-date").val() || frappe.datetime.get_today(),
                currency: $("#ai-currency").val() || "IQD",
                gift: $("#ai-gift").is(":checked"),
                priority: $("#ai-priority").val() || null,
                governorate_of_delivery: $("#ai-gov-delivery").val().trim(),
                discount_amount: parseFloat($("#ai-discount-amount").val()) || 0,
                custom_details: $("#ai-custom-details").val().trim(),
                order_items,
            };

            this.show_spinner(["Creating Sales Order..."]);

            frappe.call({
                method: "narjes_custom.ai_intake.api.confirm_intake",
                args: {
                    intake_name: this.intake_data.intake_name,
                    reviewed_data: JSON.stringify(reviewed_data),
                },
                callback: (r) => {
                    this.clear_spinner_interval();
                    if (r.exc) { this.show_error(r.exc); return; }
                    this.render_success_screen(r.message);
                },
                error: (err) => {
                    this.clear_spinner_interval();
                    this.show_error(String(err));
                },
            });
        }

        render_success_screen(result) {
            const $main = $(this.wrapper).find(".layout-main-section");
            $main.html(`
                <div class="ai-intake-wrap">
                    <div class="ai-intake-card" style="text-align:center;border-color:#6ee7b7;background:#d1fae5;">
                        <h3 style="color:#065f46;margin-bottom:12px;">🎉 Order Created Successfully!</h3>
                        <p style="color:#065f46;">
                            ${result.created_new_customer ? "A new customer was created and a " : "A "}
                            Sales Order has been created.
                        </p>
                        <div style="display:flex;gap:12px;justify-content:center;margin-top:20px;">
                            <a href="/app/sales-order/${result.sales_order}" target="_blank" class="btn btn-primary">
                                📄 View Sales Order: ${result.sales_order}
                            </a>
                            <a href="/app/customer/${encodeURIComponent(result.customer)}" target="_blank" class="btn btn-default">
                                👤 View Customer: ${result.customer}
                            </a>
                        </div>
                    </div>
                    <button class="btn btn-default" id="ai-new-intake-btn" style="margin-top:10px;">➕ Process another order</button>
                </div>
            `);
            $("#ai-new-intake-btn").on("click", () => this.render_intake_screen());
        }

        show_spinner(steps = ["Processing..."]) {
            const $main = $(this.wrapper).find(".layout-main-section");
            
            // Cycle through steps if multiple are provided
            let stepHtml = '';
            steps.forEach((s, i) => {
                stepHtml += `<div class="ai-loading-step ${i === 0 ? 'active' : ''}">${s}</div>`;
            });

            $main.html(`
                <div class="ai-intake-wrap">
                    <div class="ai-intake-card ai-spinner-wrap">
                        <div class="spinner-border text-primary" role="status" style="width:30px;height:30px;border-width:3px;"></div>
                        <div id="ai-loading-steps" style="display:flex;flex-direction:column;align-items:center;gap:4px;">
                            ${stepHtml}
                        </div>
                    </div>
                </div>
            `);

            if (steps.length > 1) {
                let current = 0;
                this.spinnerInterval = setInterval(() => {
                    current++;
                    if (current >= steps.length) current = steps.length - 1; // stay on last step
                    const $steps = $("#ai-loading-steps .ai-loading-step");
                    $steps.removeClass("active");
                    $steps.eq(current).addClass("active");
                }, 1500); // Change step every 1.5s
            }
        }

        clear_spinner_interval() {
            if (this.spinnerInterval) {
                clearInterval(this.spinnerInterval);
                this.spinnerInterval = null;
            }
        }

        show_error(msg) {
            this.clear_spinner_interval();
            const $main = $(this.wrapper).find(".layout-main-section");
            $main.html(`
                <div class="ai-intake-wrap">
                    <div class="ai-intake-card" style="border-color:var(--red);">
                        <h4><span style="font-size:18px">❌</span> Error</h4>
                        <pre style="white-space:pre-wrap;font-size:13px;color:var(--red);background:#fef2f2;padding:12px;border-radius:4px;">${frappe.utils.escape_html(String(msg))}</pre>
                        <button class="btn btn-default" id="ai-retry-btn" style="margin-top:14px;">← Back to intake</button>
                    </div>
                </div>
            `);
            $("#ai-retry-btn").on("click", () => this.render_intake_screen());
        }

        show_duplicate_warning(data) {
            this.clear_spinner_interval();
            const $main = $(this.wrapper).find(".layout-main-section");
            $main.html(`
                <div class="ai-intake-wrap">
                    <div class="ai-intake-card" style="border-color:#f59e0b;background:#fffbeb;">
                        <h4 style="color:#d97706;"><span style="font-size:18px">⚠️</span> Duplicate Detected</h4>
                        <p style="color:#92400e;font-size:14px;margin-bottom:20px;">${frappe.utils.escape_html(data.message)}</p>
                        <a href="/app/sales-order/${data.created_sales_order}" target="_blank" class="btn btn-primary">
                            View existing Sales Order: ${data.created_sales_order}
                        </a>
                        <br/><br/>
                        <button class="btn btn-default" id="ai-back-dup-btn">← Process a different order</button>
                    </div>
                </div>
            `);
            $("#ai-back-dup-btn").on("click", () => this.render_intake_screen());
        }

        show_extraction_failed(data) {
            this.clear_spinner_interval();
            const $main = $(this.wrapper).find(".layout-main-section");
            $main.html(`
                <div class="ai-intake-wrap">
                    <div class="ai-intake-card" style="border-color:var(--red);">
                        <h4><span style="font-size:18px">❌</span> Extraction Failed</h4>
                        <p style="color:var(--red);font-size:13px;background:#fef2f2;padding:12px;border-radius:4px;">${frappe.utils.escape_html(data.error_message || "Unknown error")}</p>
                        <p style="font-size:13px;color:var(--text-muted);margin-top:14px;">
                            The attempt has been saved as <strong>${data.intake_name}</strong> (status: Failed).
                            Please enter the order manually or fix the issue and try again.
                        </p>
                        <button class="btn btn-default" id="ai-back-fail-btn" style="margin-top:14px;">← Back to intake</button>
                    </div>
                </div>
            `);
            $("#ai-back-fail-btn").on("click", () => this.render_intake_screen());
        }
    }

    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "AI Order Intake",
        single_column: true,
    });

    // Inject CSS
    const style = document.createElement("style");
    style.textContent = AI_INTAKE_CSS;
    document.head.appendChild(style);

    const app = new AIOrderIntakePage(page, wrapper);
    wrapper.ai_intake_app = app;
};