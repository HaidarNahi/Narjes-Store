// Copyright (c) 2026, Narjes Custom and contributors
// For license information, please see license.txt

/* global frappe, $, __ */

/**
 * Debts — who owes us, and what we owe.
 *
 * Same loading approach as the salaries page: a skeleton of the real layout
 * on the first frame, and filter changes dim the current rows rather than
 * blanking them, so the page never flashes empty on a slow connection.
 *
 * Instalment plans are fetched only when a row is opened. Most debts are paid
 * in one go, so loading every plan up front would cost a query per debt to
 * show nothing.
 */

frappe.pages["narjes-debts"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Debts"),
		single_column: true,
	});
	new DebtsDashboard(page, wrapper);
};

const STATUS_ORDER = ["Overdue", "Partly settled", "Open", "Settled"];

class DebtsDashboard {
	constructor(page, wrapper) {
		this.page = page;
		this.$main = $(wrapper).find(".layout-main-section");
		this.filter = { status: "", direction: "" };
		this.plans = new Map();
		// See the salaries page: two quick filter clicks otherwise let the
		// slower response win and show rows that do not match the buttons.
		this.request = 0;

		this.page.set_primary_action(__("New debt"), () =>
			frappe.new_doc("Narjes Debt", {}, (doc) => {
				doc.debt_date = frappe.datetime.get_today();
			})
		);

		this.render_shell();
		this.load();
	}

	render_shell() {
		this.$main.html(`
			<div class="ndbt">
				<div class="ndbt-head">
					<div class="ndbt-filters" data-dir>
						<button class="ndbt-btn is-on" data-direction="">${__("Both ways")}</button>
						<button class="ndbt-btn" data-direction="They owe us">${__("They owe us")}</button>
						<button class="ndbt-btn" data-direction="We owe them">${__("We owe them")}</button>
					</div>
					<div class="ndbt-filters" data-status>
						<button class="ndbt-btn is-on" data-status="">${__("All")}</button>
						<button class="ndbt-btn" data-status="Overdue">${__("Overdue")}</button>
						<button class="ndbt-btn" data-status="Open">${__("Open")}</button>
						<button class="ndbt-btn" data-status="Settled">${__("Settled")}</button>
					</div>
				</div>
				<div class="ndbt-body" data-body></div>
			</div>
		`);

		this.$body = this.$main.find("[data-body]");

		this.$main.on("click", "[data-direction]", (e) => {
			const $b = $(e.currentTarget);
			this.filter.direction = $b.data("direction");
			$b.siblings().removeClass("is-on");
			$b.addClass("is-on");
			this.load();
		});
		this.$main.on("click", "[data-status]", (e) => {
			const $b = $(e.currentTarget);
			this.filter.status = $b.data("status");
			$b.siblings().removeClass("is-on");
			$b.addClass("is-on");
			this.load();
		});
		this.$main.on("click", "[data-open-debt]", (e) => {
			e.preventDefault();
			frappe.set_route("Form", "Narjes Debt", $(e.currentTarget).data("open-debt"));
		});
		this.$main.on("click", "[data-toggle-plan]", (e) => this.toggle_plan(e));
	}

	async load() {
		const token = ++this.request;
		if (this.$body.children().length) {
			this.$body.addClass("is-busy");
		} else {
			this.render_skeleton();
		}

		try {
			const r = await frappe.call({
				method: "narjes_custom.debts.get_dashboard",
				args: { status: this.filter.status, direction: this.filter.direction },
			});
			if (token !== this.request) return;
			this.render(r.message);
		} catch (e) {
			if (token !== this.request) return;
			this.render_error(e);
		} finally {
			if (token === this.request) this.$body.removeClass("is-busy");
		}
	}

	render_skeleton() {
		const card = `<div class="ndbt-card"><div class="ndbt-skel ndbt-skel--line" style="width:50%"></div>
			<div class="ndbt-skel ndbt-skel--val"></div></div>`;
		this.$body.html(`
			<div class="ndbt-cards">${card.repeat(4)}</div>
			<div class="ndbt-tablewrap" style="padding:12px">
				${`<div class="ndbt-skel ndbt-skel--row"></div>`.repeat(5)}
			</div>
		`);
	}

	render_error(err) {
		const msg = (err && (err.message || err.responseText)) || __("Something went wrong.");
		this.$body.html(`
			<div class="ndbt-empty">
				<div class="ndbt-empty__t">${__("Could not load the debts")}</div>
				<div style="margin-bottom:14px">${frappe.utils.escape_html(String(msg)).slice(0, 300)}</div>
				<button class="ndbt-btn ndbt-btn--primary" onclick="location.reload()">${__("Try again")}</button>
			</div>
		`);
	}

	render(data) {
		const money = (v) => format_currency(v, frappe.defaults.get_default("currency"));
		const s = data.summary;

		const cards = `
			<div class="ndbt-cards">
				<div class="ndbt-card ndbt-card--in">
					<div class="ndbt-card__lbl">${__("Owed to us")}</div>
					<div class="ndbt-card__val">${money(s.owed_to_us)}</div>
					<div class="ndbt-card__sub">${__("{0} debtors", [s.owed_to_us_count])}</div>
				</div>
				<div class="ndbt-card ndbt-card--out">
					<div class="ndbt-card__lbl">${__("We owe")}</div>
					<div class="ndbt-card__val">${money(s.we_owe)}</div>
					<div class="ndbt-card__sub">${__("{0} creditors", [s.we_owe_count])}</div>
				</div>
				<div class="ndbt-card ndbt-card--net">
					<div class="ndbt-card__lbl">${__("Net position")}</div>
					<div class="ndbt-card__val">${s.net_position >= 0 ? "+" : ""}${money(s.net_position)}</div>
					<div class="ndbt-card__sub">${
						s.net_position >= 0 ? __("in your favour") : __("against you")
					}</div>
				</div>
				<div class="ndbt-card ndbt-card--late">
					<div class="ndbt-card__lbl">${__("Overdue")}</div>
					<div class="ndbt-card__val">${money(s.overdue_total)}</div>
					<div class="ndbt-card__sub">${
						s.overdue_count
							? __("{0} debts · worst {1} days late", [s.overdue_count, s.worst_overdue_days])
							: __("nothing late")
					}</div>
				</div>
			</div>`;

		if (!data.debts.length) {
			this.$body.html(`
				<div class="ndbt-in">${cards}
					<div class="ndbt-empty">
						<div class="ndbt-empty__t">${__("Nothing here")}</div>
						<div style="margin-bottom:14px">${
							this.filter.status || this.filter.direction
								? __("No debts match these filters.")
								: __("No debts have been recorded yet.")
						}</div>
					</div>
				</div>`);
			return;
		}

		this.$body.html(`<div class="ndbt-in">${cards}${this.table(data.debts, money)}</div>`);
	}

	table(debts, money) {
		const rows = debts.map((d) => this.row(d, money)).join("");
		return `
			<div class="ndbt-tablewrap">
				<table class="ndbt-table">
					<thead><tr>
						<th>${__("Who")}</th>
						<th>${__("Taken on")}</th>
						<th>${__("Settle by")}</th>
						<th class="ndbt-num">${__("Amount")}</th>
						<th class="ndbt-num">${__("Paid")}</th>
						<th class="ndbt-num">${__("Still owed")}</th>
						<th>${__("Status")}</th>
						<th>${__("Plan")}</th>
					</tr></thead>
					<tbody>${rows}</tbody>
				</table>
			</div>`;
	}

	row(d, money) {
		const tone =
			{
				Overdue: "overdue",
				"Partly settled": "partly",
				Open: "open",
				Settled: "settled",
			}[d.status] || "open";

		const status =
			d.status === "Overdue"
				? __("{0} days late", [d.days_overdue])
				: d.status === "Partly settled"
				? __("{0} of {1} paid", [d.instalments_paid, d.instalments])
				: __(d.status);

		const plan = d.instalments
			? `<button class="ndbt-btn" data-toggle-plan="${d.name}" style="padding:2px 8px;font-size:12px">
					${__("{0} instalments", [d.instalments])}</button>`
			: `<span style="color:var(--n-text-3)">${__("one payment")}</span>`;

		return `
			<tr class="ndbt-row ndbt-row--${tone}" data-row="${d.name}">
				<td>
					<div class="ndbt-who" data-open-debt="${d.name}">${frappe.utils.escape_html(
						d.display_name || d.name
					)}</div>
					<div class="ndbt-dir">${__(d.direction)}</div>
				</td>
				<td>${d.debt_date ? frappe.datetime.str_to_user(d.debt_date) : "—"}</td>
				<td>${d.due_date ? frappe.datetime.str_to_user(d.due_date) : "—"}</td>
				<td class="ndbt-num">${money(d.amount)}</td>
				<td class="ndbt-num">${d.paid_amount ? money(d.paid_amount) : "—"}</td>
				<td class="ndbt-num"><b>${d.outstanding ? money(d.outstanding) : "—"}</b></td>
				<td><span class="ndbt-pill ndbt-pill--${tone}">${status}</span></td>
				<td>${plan}</td>
			</tr>`;
	}

	async toggle_plan(e) {
		const name = $(e.currentTarget).data("toggle-plan");
		const $row = this.$main.find(`[data-row="${name}"]`);
		const $existing = this.$main.find(`[data-plan="${name}"]`);

		if ($existing.length) {
			$existing.remove();
			return;
		}

		// Placeholder inserted first, so the row opens the instant it is
		// clicked rather than after the round trip.
		const cols = $row.children().length;
		$row.after(
			`<tr class="ndbt-plan" data-plan="${name}"><td colspan="${cols}">
				<div class="ndbt-plan__loading">${__("Loading the plan…")}</div>
			</td></tr>`
		);
		const $panel = this.$main.find(`[data-plan="${name}"] td`);

		try {
			let rows = this.plans.get(name);
			if (!rows) {
				const r = await frappe.call({
					method: "narjes_custom.debts.get_settlements",
					args: { debt: name },
				});
				rows = r.message || [];
				this.plans.set(name, rows);
			}
			$panel.html(this.plan_html(rows));
		} catch (err) {
			$panel.html(
				`<div class="ndbt-plan__loading">${__("Could not load this plan.")}</div>`
			);
		}
	}

	plan_html(rows) {
		const money = (v) => format_currency(v, frappe.defaults.get_default("currency"));
		if (!rows.length) {
			return `<div class="ndbt-plan__loading">${__("No instalments scheduled.")}</div>`;
		}
		const body = rows
			.map(
				(r) => `<tr>
					<td class="ndbt-plan__cell">${r.idx}</td>
					<td class="ndbt-plan__cell">${
						r.due_date ? frappe.datetime.str_to_user(r.due_date) : "—"
					}</td>
					<td class="ndbt-plan__cell">${
						r.paid_on ? frappe.datetime.str_to_user(r.paid_on) : "—"
					}</td>
					<td class="ndbt-plan__cell">${
						r.mode_of_payment ? frappe.utils.escape_html(r.mode_of_payment) : "—"
					}</td>
					<td class="ndbt-plan__cell ndbt-num">${money(r.amount)}</td>
					<td class="ndbt-plan__cell">
						<span class="ndbt-pill ndbt-pill--${r.paid_on ? "settled" : "open"}">
							${r.paid_on ? __("Paid") : __("Scheduled")}</span>
					</td>
				</tr>`
			)
			.join("");

		const left = rows.filter((r) => !r.paid_on).reduce((a, r) => a + r.amount, 0);
		return `
			<div class="ndbt-plan__inner">
				<table>
					<thead><tr>
						<th>#</th><th>${__("Due")}</th><th>${__("Paid on")}</th>
						<th>${__("How")}</th><th class="ndbt-num">${__("Amount")}</th><th>${__("Status")}</th>
					</tr></thead>
					<tbody>${body}</tbody>
				</table>
				<div style="margin-top:8px;font-size:12.5px;color:var(--n-text-2)">
					${__("Still to pay")}: <b class="ndbt-num">${money(left)}</b>
				</div>
			</div>`;
	}
}
