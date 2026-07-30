"""Narjes Ledger server-side branding (theme plan P8/P9): Letter Head,
Print Style, help-menu prune. Idempotent — follows the same setup-module
pattern as branding.py and runs on after_migrate so a fresh site converges.

Run via: bench execute narjes_custom.setup.theme_branding.run
"""

import frappe

LOGO = "/assets/narjes_custom/images/narjes-logo.svg"

LETTER_HEAD_HTML = f"""
<div style="display: flex; align-items: center; justify-content: space-between;
	border-bottom: 2px solid #2E5C46; padding-bottom: 12px; margin-bottom: 16px;">
	<div style="display: flex; align-items: center; gap: 12px;">
		<img src="{LOGO}" alt="Narjes" style="width: 44px; height: 44px;">
		<div>
			<div style="font-family: Fraunces, Georgia, serif; font-size: 20px;
				font-weight: 600; color: #1B211D;">Narjes Store</div>
			<div style="font-family: Amiri, serif; font-size: 13px; color: #4C544E;">
				&#1606;&#1585;&#1580;&#1587; &#1587;&#1578;&#1608;&#1585;</div>
		</div>
	</div>
	<div style="font-family: 'IBM Plex Mono', monospace; font-size: 11px;
		color: #4C544E; text-align: right;">
		Baghdad · Iraq<br>haimohx@gmail.com
	</div>
</div>
"""

LETTER_HEAD_FOOTER = """
<div style="border-top: 1px solid #D7DCD7; margin-top: 16px; padding-top: 8px;
	font-family: 'IBM Plex Mono', monospace; font-size: 10px; color: #6A736C;
	text-align: center;">
	Narjes Store · Baghdad
</div>
"""

# Ledger print voice: embedded brand faces (server-installed for the PDF
# engine, P2.10), mono tables with hairline rules, stamps that read by shape
# in pure grayscale.
PRINT_STYLE_CSS = """
.print-format {
	font-family: "IBM Plex Sans", "IBM Plex Sans Arabic", sans-serif;
	font-size: 9pt;
	color: #1B211D;
}
.print-format h1, .print-format h2, .print-format h3 {
	font-family: "Fraunces", "Amiri", Georgia, serif;
	font-weight: 600;
}
.print-format table.table {
	font-family: "IBM Plex Mono", monospace;
	font-variant-numeric: tabular-nums;
	font-size: 8.5pt;
}
.print-format table.table th {
	font-size: 7.5pt;
	text-transform: uppercase;
	letter-spacing: 0.06em;
	color: #4C544E;
	border-bottom: 1px solid #4C544E !important;
}
.print-format table.table td, .print-format table.table th {
	border-color: #D7DCD7;
	padding: 4px 6px;
}
.print-format .text-right, .print-format td[style*="text-align: right"] {
	font-variant-numeric: tabular-nums;
}
/* docstatus stamp: shape-coded so it survives grayscale */
.print-format .n-print-stamp {
	display: inline-block;
	transform: rotate(-2deg);
	border: 2px double #1B211D;
	border-radius: 4px;
	padding: 2px 10px;
	font-family: "IBM Plex Mono", monospace;
	font-size: 9pt;
	letter-spacing: 0.1em;
	text-transform: uppercase;
}
"""


# P5.4 state table → Kanban Board "Order Phases" column indicators. Named
# colors resolve through the Lever-1 ramp remap (green→fern, orange→saffron,
# red→stamp, gray→neutral), so the board always rides the exact brand ramps.
KANBAN_COLUMN_COLORS = {
	"New": "Green",
	"In Design": "Orange",
	"Waiting Approval": "Orange",
	"Ready to Execution": "Green",
	"Execution": "Green",
	"Waiting": "Gray",
	"In Delivery": "Green",
	"Done": "Green",
	"Cancelled": "Red",
	"Returned": "Red",
}


# P9.3 — Jinja print formats (versionable in git, not builder-made).
# Customer copy: ledger tables, stamped status, IQD mono totals.
SO_PRINT_FORMAT_HTML = """
{%- set status_color = "#9B3B3B" if doc.docstatus == 2 else "#2E5C46" -%}
<div style="font-family: 'IBM Plex Sans', 'IBM Plex Sans Arabic', sans-serif; color: #1B211D;">
	<div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px;">
		<div>
			<h2 style="font-family: Fraunces, Amiri, Georgia, serif; margin: 0;">
				{{ _("Order") }} <span style="font-family: 'IBM Plex Mono', monospace;">{{ doc.name }}</span>
			</h2>
			<div style="font-family: 'IBM Plex Mono', monospace; font-size: 10pt; color: #4C544E;">
				{{ frappe.utils.formatdate(doc.transaction_date, "dd-MM-yyyy") }}
			</div>
		</div>
		<div class="n-print-stamp" style="color: {{ status_color }}; border-color: {{ status_color }};">
			{{ _(doc.status) }}
		</div>
	</div>

	<table style="width: 100%; font-size: 10pt; margin-bottom: 12px;">
		<tr>
			<td style="width: 50%; vertical-align: top;">
				<div style="font-size: 8pt; text-transform: uppercase; letter-spacing: 0.06em; color: #6A736C;">{{ _("Customer") }}</div>
				<div style="font-size: 13pt; font-weight: 600;">{{ doc.customer_name or doc.customer }}</div>
				{%- if doc.contact_mobile -%}
				<div style="font-family: 'IBM Plex Mono', monospace;">{{ doc.contact_mobile }}</div>
				{%- endif -%}
			</td>
			<td style="width: 50%; vertical-align: top; text-align: right;">
				<div style="font-size: 8pt; text-transform: uppercase; letter-spacing: 0.06em; color: #6A736C;">{{ _("Delivery") }}</div>
				<div>{{ frappe.utils.formatdate(doc.delivery_date, "dd-MM-yyyy") if doc.delivery_date else "—" }}</div>
				{%- if doc.get("custom_governorate") -%}<div>{{ doc.custom_governorate }}</div>{%- endif -%}
			</td>
		</tr>
	</table>

	<table class="table" style="width: 100%; border-collapse: collapse;">
		<thead>
			<tr>
				<th style="text-align: left;">{{ _("Item") }}</th>
				<th style="text-align: right;">{{ _("Qty") }}</th>
				<th style="text-align: right;">{{ _("Rate") }}</th>
				<th style="text-align: right;">{{ _("Amount") }}</th>
			</tr>
		</thead>
		<tbody>
			{%- for row in doc.items -%}
			<tr>
				<td>{{ row.item_name }}
					{%- if row.get("custom_area") %} <span style="color:#6A736C;">({{ row.custom_area }})</span>{% endif -%}
				</td>
				<td style="text-align: right;">{{ row.get_formatted("qty") }}</td>
				<td style="text-align: right;">{{ row.get_formatted("rate") }}</td>
				<td style="text-align: right;">{{ row.get_formatted("amount") }}</td>
			</tr>
			{%- endfor -%}
		</tbody>
	</table>

	<table style="width: 40%; margin-left: auto; font-family: 'IBM Plex Mono', monospace; font-size: 10pt; margin-top: 8px;">
		<tr><td>{{ _("Total") }}</td><td style="text-align: right;">{{ doc.get_formatted("total") }}</td></tr>
		{%- for tax in doc.taxes -%}
		<tr><td>{{ tax.description }}</td><td style="text-align: right;">{{ tax.get_formatted("tax_amount") }}</td></tr>
		{%- endfor -%}
		<tr style="font-weight: 600; border-top: 1.5px solid #1B211D;">
			<td>{{ _("Grand Total") }}</td><td style="text-align: right;">{{ doc.get_formatted("grand_total") }}</td>
		</tr>
	</table>
</div>
"""

# Driver slip (A5): oversized name + phone + COD — built for a pocket.
DRIVER_SLIP_HTML = """
<div style="font-family: 'IBM Plex Sans', 'IBM Plex Sans Arabic', sans-serif; color: #1B211D; padding: 4mm;">
	<div style="font-family: 'IBM Plex Mono', monospace; font-size: 12pt; margin-bottom: 4mm;">{{ doc.name }}</div>
	<div style="font-size: 20pt; font-weight: 700; margin-bottom: 2mm;">{{ doc.customer_name or doc.customer }}</div>
	<div style="font-family: 'IBM Plex Mono', monospace; font-size: 18pt; margin-bottom: 4mm;">
		{{ doc.contact_mobile or doc.contact_phone or "—" }}
	</div>
	<div style="font-size: 14pt; margin-bottom: 6mm;">
		{{ doc.get("custom_governorate") or "" }} {{ doc.address_display or "" }}
	</div>
	<div style="border: 2px solid #1B211D; border-radius: 4px; padding: 4mm; text-align: center;">
		<div style="font-size: 9pt; text-transform: uppercase; letter-spacing: 0.08em;">{{ _("Collect (COD)") }}</div>
		<div style="font-family: 'IBM Plex Mono', monospace; font-size: 24pt; font-weight: 700;">
			{{ doc.get_formatted("grand_total") }}
		</div>
	</div>
</div>
"""


def run():
	_letter_head()
	_print_style()
	_print_formats()
	_prune_help_menu()
	_kanban_colors()
	frappe.db.commit()
	print(
		"Applied Narjes Ledger branding: Letter Head, Print Style, "
		"print formats, help menu, kanban colors"
	)


def _print_formats():
	formats = [
		("Narjes Order", "Sales Order", SO_PRINT_FORMAT_HTML),
		("Narjes Driver Slip", "Delivery Note", DRIVER_SLIP_HTML),
	]
	for name, doctype, html in formats:
		if frappe.db.exists("Print Format", name):
			pf = frappe.get_doc("Print Format", name)
		else:
			pf = frappe.new_doc("Print Format")
			pf.name = name
		pf.doc_type = doctype
		pf.module = "Narjes Custom"
		pf.custom_format = 1
		pf.print_format_type = "Jinja"
		pf.html = html
		pf.disabled = 0
		pf.save(ignore_permissions=True)


def _letter_head():
	if frappe.db.exists("Letter Head", "Narjes"):
		lh = frappe.get_doc("Letter Head", "Narjes")
	else:
		lh = frappe.new_doc("Letter Head")
		lh.letter_head_name = "Narjes"
	lh.source = "HTML"
	lh.content = LETTER_HEAD_HTML
	lh.footer_source = "HTML"
	lh.footer = LETTER_HEAD_FOOTER
	lh.is_default = 1
	lh.disabled = 0
	lh.save(ignore_permissions=True)


def _print_style():
	if frappe.db.exists("Print Style", "Narjes Ledger"):
		ps = frappe.get_doc("Print Style", "Narjes Ledger")
	else:
		ps = frappe.new_doc("Print Style")
		ps.print_style_name = "Narjes Ledger"
	ps.disabled = 0
	ps.css = PRINT_STYLE_CSS
	ps.save(ignore_permissions=True)

	print_settings = frappe.get_single("Print Settings")
	print_settings.print_style = "Narjes Ledger"
	print_settings.save(ignore_permissions=True)


def _kanban_colors():
	if not frappe.db.exists("Kanban Board", "Order Phases"):
		return
	board = frappe.get_doc("Kanban Board", "Order Phases")
	changed = False
	for column in board.columns:
		wanted = KANBAN_COLUMN_COLORS.get(column.column_name)
		if wanted and column.indicator != wanted:
			column.indicator = wanted
			changed = True
	if changed:
		board.save(ignore_permissions=True)


def _prune_help_menu():
	"""Drop framework links from the help dropdown (theme plan P8.2): keep
	Keyboard Shortcuts + About (the About dialog itself is rebranded by the
	narjes.bundle.js shim)."""
	navbar = frappe.get_single("Navbar Settings")
	drop = {"documentation", "user forum", "report an issue", "frappe support"}
	for row in navbar.help_dropdown:
		if (row.item_label or "").strip().lower() in drop:
			row.hidden = 1
	navbar.save(ignore_permissions=True)
