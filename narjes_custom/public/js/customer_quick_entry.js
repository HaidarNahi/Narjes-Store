// Override the Customer Quick Entry to hide
// "Primary Contact Details" and "Primary Address Details" sections.
// We keep only the doctype's own quick-entry fields (customer_name, etc.)

frappe.ui.form.CustomerQuickEntryForm = class CustomerQuickEntryForm extends (
    frappe.ui.form.QuickEntryForm
) {
    constructor(doctype, after_insert, init_callback, doc, force) {
        super(doctype, after_insert, init_callback, doc, force);
        this.skip_redirect_on_error = true;
    }

    // Return empty array — no contact/address sections
    get_variant_fields() {
        return [];
    }

    render_dialog() {
        this.mandatory = this.mandatory.concat(this.get_variant_fields());
        super.render_dialog();
    }
};

// Auto-redirect Desk home landing page to narjes-home
window.has_redirected_to_narjes_home = false;

frappe.router.on('change', function() {
    let route = frappe.get_route();
    if (!route) return;
    
    let is_landing = (route[0] === 'workspace' || route[0] === 'home' || route.length === 0);
    let is_broken_sidebar = (route.includes('narjes-dashboard') || route.includes('Narjes Dashboard'));

    if (is_broken_sidebar) {
        // ALWAYS redirect if they click the broken sidebar link
        setTimeout(() => { frappe.set_route('narjes-home'); }, 10);
    } else if (is_landing) {
        // Only redirect once on initial load
        if (!window.has_redirected_to_narjes_home) {
            window.has_redirected_to_narjes_home = true;
            setTimeout(() => { frappe.set_route('narjes-home'); }, 10);
        }
    }
});

// Force sidebar cache clear once
if (!localStorage.getItem('narjes_sidebar_cleared')) {
    Object.keys(localStorage).forEach(key => {
        if (key.includes('sidebar_items') || key.includes('workspace')) {
            localStorage.removeItem(key);
        }
    });
    localStorage.setItem('narjes_sidebar_cleared', '1');
}

$(document).ready(function() {
    setTimeout(() => {
        $('.navbar-brand').off('click').on('click', function(e) {
            e.preventDefault();
            frappe.set_route('narjes-home');
        });

        // Fixed, centered Home button in the navbar — always reachable from anywhere in the desk
        if (!document.getElementById('narjes-navbar-home-btn')) {
            $('<button>', {
                id: 'narjes-navbar-home-btn',
                class: 'narjes-navbar-home-btn',
                title: __('Go to Home'),
                html: '<span class="narjes-navbar-home-icon">🏠</span>'
            })
                .on('click', function(e) {
                    e.preventDefault();
                    frappe.set_route('narjes-home');
                })
                .appendTo('body');
        }
    }, 1000);
});

