frappe.pages['narjes-home'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Home Dashboard',
        single_column: true
    });

    new NarjesHomeDashboard(page, wrapper);
};

var NarjesHomeDashboard = class {
    constructor(page, wrapper) {
        this.page = page;
        this.wrapper = wrapper;
        
        // Load settings from LocalStorage or defaults
        this.config = this.get_config();
        this.shortcuts = this.get_shortcuts();
        
        this.init_page();
    }

    get_config() {
        const saved = localStorage.getItem('narjes_home_config');
        if (saved) {
            try { return JSON.parse(saved); } catch (e) {}
        }
        const defaults = (frappe.boot && frappe.boot.narjes_settings) || {};
        return {
            show_ai_intake: defaults.default_show_ai_intake !== false,
            show_shortcuts: defaults.default_show_shortcuts !== false,
            show_analytics: defaults.default_show_analytics !== false
        };
    }

    save_config(config) {
        this.config = config;
        localStorage.setItem('narjes_home_config', JSON.stringify(config));
        this.render();
    }

    get_shortcuts() {
        // Shortcuts are configured centrally in Narjes Settings (System Manager
        // only) so a "Role" can be attached to each one. Filter here to only
        // what the current user is allowed to see.
        const all = (frappe.boot && frappe.boot.narjes_settings && frappe.boot.narjes_settings.shortcuts) || [];
        return all.filter((sc) => !sc.role || (frappe.user_roles || []).includes(sc.role));
    }

    init_page() {
        // narjes_home.css is loaded automatically by Frappe (Page.load_assets
        // injects it as an inline <style> alongside this script) — no manual
        // <link> needed here.
        this.render();
    }

    render() {
        const $main = $(this.wrapper).find('.layout-main-section');
        $main.html(`
            <div class="narjes-home-wrapper">
                <!-- Hero Banner Header -->
                <div class="narjes-hero-banner">
                    <div class="narjes-hero-title">
                        <h2><span class="brand-dot"></span> Narjes Store Workspace</h2>
                        <p>Welcome to your central management hub & fast AI order portal</p>
                    </div>
                    <div class="narjes-header-actions">
                        <button class="btn-narjes-customize" id="btn-customize-home">
                            ${narjes_icon('gear-six')} Customize Home
                        </button>
                    </div>
                </div>

                <!-- 1. AI Order Intake Section -->
                ${this.config.show_ai_intake ? `
                <div class="narjes-section-card" id="section-ai-intake">
                    <div class="narjes-section-header">
                        <h3>${narjes_icon('sparkle')} AI Fast Order Intake</h3>
                        <span style="font-size:12px;color:var(--narjes-muted);">Paste customer message below to extract order instantly</span>
                    </div>
                    <div class="narjes-ai-box">
                        <textarea 
                            class="narjes-ai-textarea" 
                            id="home-ai-raw-text" 
                            placeholder="Paste WhatsApp or informal customer order here... (e.g. احمد / 07701234567 / MDF 30*40 قطعتين / التوصيل بغداد...)" 
                            dir="auto"
                        ></textarea>
                        <div class="narjes-ai-actions">
                            <button class="btn btn-default btn-sm" id="btn-clear-home-ai">Clear</button>
                            <button class="btn-narjes-primary" id="btn-process-home-ai">
                                ${narjes_icon('sparkle')} Extract & Process Order
                            </button>
                        </div>
                    </div>
                </div>
                ` : ''}

                <!-- 2. Customizable Shortcuts Bar Section -->
                ${this.config.show_shortcuts ? `
                <div class="narjes-section-card" id="section-shortcuts">
                    <div class="narjes-section-header">
                        <h3>${narjes_icon('link-simple')} Quick Shortcuts</h3>
                        ${frappe.user_roles.includes('System Manager') ? `
                        <button class="btn btn-xs btn-default" id="btn-manage-shortcuts">
                            ${narjes_icon('pencil-simple')} Edit Shortcuts
                        </button>
                        ` : ''}
                    </div>
                    <div class="narjes-shortcuts-grid" id="home-shortcuts-grid"></div>
                </div>
                ` : ''}

                <!-- 3. KPI Metrics Grid -->
                ${this.config.show_analytics ? `
                <div class="narjes-kpi-grid" id="home-kpi-grid">
                    <div class="narjes-kpi-card">
                        <div class="narjes-kpi-info">
                            <p>Today's Revenue</p>
                            <h4 id="kpi-today-rev">0 IQD</h4>
                        </div>
                        <div class="narjes-kpi-icon kpi-icon-mint">${narjes_icon('currency-circle-dollar', {size: 'lg'})}</div>
                    </div>
                    <div class="narjes-kpi-card">
                        <div class="narjes-kpi-info">
                            <p>Today's Orders</p>
                            <h4 id="kpi-today-orders">0</h4>
                        </div>
                        <div class="narjes-kpi-icon kpi-icon-coral">${narjes_icon('package', {size: 'lg'})}</div>
                    </div>
                    <div class="narjes-kpi-card">
                        <div class="narjes-kpi-info">
                            <p>Pending Deliveries</p>
                            <h4 id="kpi-pending-del">0</h4>
                        </div>
                        <div class="narjes-kpi-icon kpi-icon-navy">${narjes_icon('truck', {size: 'lg'})}</div>
                    </div>
                    <div class="narjes-kpi-card">
                        <div class="narjes-kpi-info">
                            <p>Total Customers</p>
                            <h4 id="kpi-customers">0</h4>
                        </div>
                        <div class="narjes-kpi-icon kpi-icon-purple">${narjes_icon('users-three', {size: 'lg'})}</div>
                    </div>
                </div>

                <!-- 4. Financial Charts Grid -->
                <div class="narjes-charts-grid" id="section-charts">
                    <div class="narjes-chart-card">
                        <h4>${narjes_icon('chart-line-up')} Income Trend (Sales)</h4>
                        <div class="narjes-chart-wrapper" id="chart-income"></div>
                    </div>
                    <div class="narjes-chart-card">
                        <h4>${narjes_icon('trend-down')} Outcome Trend (Purchases)</h4>
                        <div class="narjes-chart-wrapper" id="chart-outcome"></div>
                    </div>
                    <div class="narjes-chart-card">
                        <h4>${narjes_icon('currency-circle-dollar')} Net Revenue Trend</h4>
                        <div class="narjes-chart-wrapper" id="chart-revenue"></div>
                    </div>
                </div>
                ` : ''}
            </div>
        `);

        this.bind_events();
        if (this.config.show_shortcuts) this.render_shortcuts_grid();
        if (this.config.show_analytics) this.load_analytics_data();
    }

    bind_events() {
        const self = this;

        // Customize Home button
        $('#btn-customize-home').on('click', () => this.show_customize_dialog());

        // AI Intake clear
        $('#btn-clear-home-ai').on('click', () => $('#home-ai-raw-text').val('').focus());

        // AI Intake process
        $('#btn-process-home-ai').on('click', () => {
            const raw_text = $('#home-ai-raw-text').val().trim();
            if (!raw_text) {
                frappe.msgprint({ message: "Please paste order text first.", indicator: "orange" });
                return;
            }

            // Redirect to AI intake page with text or open processing dialog
            frappe.set_route('ai-intake').then(() => {
                setTimeout(() => {
                    if ($('#ai-raw-text').length) {
                        $('#ai-raw-text').val(raw_text);
                        $('#ai-process-btn').click();
                    }
                }, 300);
            });
        });

        // Manage Shortcuts — edited via Narjes Settings' Quick Shortcuts table
        // (gives a real editable grid with a working Role autocomplete).
        $('#btn-manage-shortcuts').on('click', () => {
            frappe.set_route('Form', 'Narjes Settings').then(() => {
                setTimeout(() => {
                    if (cur_frm) cur_frm.scroll_to_field('quick_shortcuts');
                }, 300);
            });
        });
    }

    render_shortcuts_grid() {
        const $grid = $('#home-shortcuts-grid');
        if (!$grid.length) return;

        $grid.empty();
        this.shortcuts.forEach((sc, idx) => {
            // Icon values are either a raw emoji (legacy / freely-typed by an
            // admin) or a Phosphor icon name (the new default seed data) —
            // is_emoji() tells us which rendering path to take so both keep
            // working without forcing a hard data migration.
            const icon_value = sc.icon || 'link-simple';
            const icon_html = frappe.utils.is_emoji(icon_value) ? icon_value : narjes_icon(icon_value, {size: 'md'});
            const $card = $(`
                <div class="narjes-shortcut-card" data-route="${sc.route}">
                    <div class="narjes-shortcut-icon">${icon_html}</div>
                    <div class="narjes-shortcut-label" title="${frappe.utils.escape_html(sc.label)}">${frappe.utils.escape_html(sc.label)}</div>
                </div>
            `);

            $card.on('click', () => frappe.set_route(sc.route.replace('/app/', '')));
            $grid.append($card);
        });
    }

    show_customize_dialog() {
        const d = new frappe.ui.Dialog({
            title: 'Customize Home Layout',
            fields: [
                {
                    fieldtype: 'Check',
                    fieldname: 'show_ai_intake',
                    label: 'Show AI Order Intake Section',
                    default: this.config.show_ai_intake
                },
                {
                    fieldtype: 'Check',
                    fieldname: 'show_shortcuts',
                    label: 'Show Shortcuts Bar',
                    default: this.config.show_shortcuts
                },
                {
                    fieldtype: 'Check',
                    fieldname: 'show_analytics',
                    label: 'Show Analytics & Financial Charts',
                    default: this.config.show_analytics
                }
            ],
            primary_action_label: 'Save Preferences',
            primary_action: (values) => {
                this.save_config(values);
                d.hide();
                frappe.show_alert({ message: 'Home preferences saved!', indicator: 'green' });
            }
        });
        d.show();
    }

    load_analytics_data() {
        frappe.call({
            method: 'narjes_custom.api.get_home_dashboard_data',
            callback: (r) => {
                if (!r.message) return;
                const { kpis, charts } = r.message;

                // Update KPI Cards
                $('#kpi-today-rev').text(format_currency(kpis.today_revenue, 'IQD', 0));
                $('#kpi-today-orders').text(kpis.today_orders);
                $('#kpi-pending-del').text(kpis.pending_deliveries);
                $('#kpi-customers').text(kpis.total_customers);

                // Render Charts
                this.render_chart('#chart-income', 'Income', charts.labels, charts.income, NARJES_BRAND.fern, 'bar');
                this.render_chart('#chart-outcome', 'Outcome', charts.labels, charts.outcome, NARJES_BRAND.saffron, 'bar');
                this.render_chart('#chart-revenue', 'Net Revenue', charts.labels, charts.net_revenue, NARJES_BRAND.ink, 'line');
            }
        });
    }

    render_chart(container, title, labels, values, color, type) {
        if (!window.frappe || !frappe.Chart) {
            // Lazy load frappe charts if needed
            frappe.require('assets/frappe/js/lib/frappe-charts/frappe-charts.min.iife.js', () => {
                this.create_frappe_chart(container, title, labels, values, color, type);
            });
        } else {
            this.create_frappe_chart(container, title, labels, values, color, type);
        }
    }

    create_frappe_chart(container, title, labels, values, color, type) {
        const el = document.querySelector(container);
        if (!el) return;

        new frappe.Chart(el, {
            title: "",
            data: {
                labels: labels,
                datasets: [
                    {
                        name: title,
                        values: values,
                        chartType: type
                    }
                ]
            },
            type: type,
            height: 200,
            colors: [color],
            axisOptions: {
                xIsSeries: true
            },
            lineOptions: {
                hideDots: 0,
                heatline: 0,
                regionFill: 1
            }
        });
    }
}
