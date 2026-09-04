// Copyright (c) 2026, Narjes Custom and contributors
// For license information, please see license.txt

/* global frappe, $, __ */

/**
 * The Revenue & Salaries.
 *
 * Loading is treated as a first-class state rather than an afterthought:
 * the page paints its own shell and a skeleton of the real layout on the
 * first frame, so there is never a blank screen, and the skeleton has the
 * same shape as the content so nothing jumps when the data lands. Changing
 * month dims the existing numbers instead of clearing them — the old figures
 * stay readable while the new ones are fetched, which on a slow connection is
 * the difference between "it's working" and "it's broken".
 */

frappe.pages["narjes-salaries"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("The Revenue & Salaries"),
		single_column: true,
	});
	new SalariesDashboard(page, wrapper);
};

class SalariesDashboard {
	constructor(page, wrapper) {
		this.page = page;
		this.$main = $(wrapper).find(".layout-main-section");
		this.month = frappe.datetime.month_start();
		// Guards against a slow response for an old month painting over a
		// newer one. Clicking ‹ twice quickly fires two requests, and without
		// this the first to *return* wins rather than the one that was asked
		// for last — which shows August's figures under a July heading.
		this.request = 0;
		// Months already fetched. Stepping back and forth through the year is
		// the main interaction here, and re-fetching a month that has not
		// changed makes it feel slower than it is.
		this.cache = new Map();

		this.render_shell();
		this.load();
	}

	// ------------------------------------------------------------- shell

	render_shell() {
		this.$main.html(`
			<div class="nsal">
				<div class="nsal-head">
					<div class="nsal-month">
						<button class="nsal-btn" data-step="-1" aria-label="${__("Previous month")}">‹</button>
						<div class="nsal-month__label" data-month-label>&nbsp;</div>
						<button class="nsal-btn" data-step="1" aria-label="${__("Next month")}">›</button>
					</div>
					<button class="nsal-btn" data-refresh>${__("Refresh")}</button>
				</div>
				<div class="nsal-body" data-body></div>
			</div>
		`);

		this.$body = this.$main.find("[data-body]");
		this.$label = this.$main.find("[data-month-label]");

		this.$main.on("click", "[data-step]", (e) => {
			this.month = frappe.datetime.add_months(this.month, +$(e.currentTarget).data("step"));
			this.load();
		});
		this.$main.on("click", "[data-refresh]", () => {
			this.cache.delete(this.month);
			this.load();
		});
		this.$main.on("click", "[data-post-commission]", (e) => this.post_commission(e));
	}

	set_label() {
		this.$label.text(
			frappe.datetime.str_to_obj(this.month).toLocaleDateString(undefined, {
				month: "long",
				year: "numeric",
			})
		);
	}

	// -------------------------------------------------------------- data

	async load() {
		const token = ++this.request;
		const month = this.month;
		this.set_label();

		const cached = this.cache.get(month);
		if (cached) {
			// Nothing to wait for — paint immediately.
			this.render(cached);
			return;
		}

		// A month never seen before gets the skeleton; a month being
		// refreshed keeps its old numbers, dimmed.
		if (this.$body.children().length) {
			this.$body.addClass("is-busy");
		} else {
			this.render_skeleton();
		}

		try {
			const r = await frappe.call({
				method: "narjes_custom.salaries.get_dashboard",
				args: { month, history_months: 6 },
			});
			this.cache.set(month, r.message);
			// A newer request has been made since this one started: its
			// answer is the one the user is waiting for, so drop this.
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
		const card = `<div class="nsal-card"><div class="nsal-skel nsal-skel--line" style="width:45%"></div>
			<div class="nsal-skel nsal-skel--val"></div></div>`;
		const row = `<div class="nsal-skel nsal-skel--row"></div>`;
		this.$body.html(`
			<div class="nsal-cards">${card.repeat(3)}</div>
			<div class="nsal-skel" style="height:30px;margin-bottom:16px"></div>
			<div class="nsal-split">
				<div>${row.repeat(3)}</div>
				<div>${row.repeat(2)}</div>
			</div>
		`);
	}

	render_error(err) {
		const msg = (err && (err.message || err.responseText)) || __("Something went wrong.");
		this.$body.html(`
			<div class="nsal-empty">
				<div class="nsal-empty__t">${__("Could not load this month")}</div>
				<div style="margin-bottom:14px">${frappe.utils.escape_html(String(msg)).slice(0, 300)}</div>
				<button class="nsal-btn nsal-btn--primary" data-refresh>${__("Try again")}</button>
			</div>
		`);
	}

	// ------------------------------------------------------------ render

	render(data) {
		const d = data.current;
		const money = (v) => format_currency(v, frappe.defaults.get_default("currency"));

		const people = d.allocations.filter((a) => a.kind === "person");
		const funds = d.allocations.filter((a) => a.kind === "fund");
		const prev = data.history[1];

		this.$body.html(`
			<div class="nsal-in">
				${this.notices(data, d)}
				${this.cards(d, money)}
				${this.allocbar(d)}
				<div class="nsal-split">
					<div>
						<div class="nsal-eyebrow">${__("This month's pay")}</div>
						${people.map((p) => this.person(p, prev, money)).join("")}
						${this.commission_person(d, prev, money)}
					</div>
					<div>
						<div class="nsal-eyebrow">${__("Kept in the business")}</div>
						<div class="nsal-boxrow">
							${funds.map((f) => this.fund(f, money)).join("")}
						</div>
						${this.commission_breakdown(d, money)}
					</div>
				</div>
				<div class="nsal-section">
					<div class="nsal-eyebrow">${__("Month by month")}</div>
					${this.history(data, money)}
				</div>
			</div>
		`);
	}

	notices(data, d) {
		let html = "";

		// The most consequential thing this page can tell you: the shares
		// below are being worked out on money that is already owed to
		// somebody else.
		if (d.commission_pending) {
			const amount = format_currency(d.commission.total, frappe.defaults.get_default("currency"));
			html += `
				<div class="nsal-notice">
					<div>
						<div class="nsal-notice__t">${__("{0}'s commission has not been recorded yet", [
							frappe.utils.escape_html(d.commission.person || __("Walaa")),
						])}</div>
						<div class="nsal-notice__b">${__(
							"Until it is, the shares below are worked out on {0} that is already owed. Recording it brings net profit to {1}.",
							[amount, format_currency(d.commission.net_if_posted, frappe.defaults.get_default("currency"))]
						)}</div>
					</div>
					${
						data.can_post_commission
							? `<button class="nsal-btn nsal-btn--primary" data-post-commission>${__(
									"Record {0}",
									[amount]
							  )}</button>`
							: ""
					}
				</div>`;
		}

		if (Math.abs(d.allocated_percent - 100) > 0.01) {
			const over = d.allocated_percent > 100;
			html += `
				<div class="nsal-notice nsal-notice--warn">
					<div>
						<div class="nsal-notice__t">${__("The shares add up to {0}%, not 100%", [
							frappe.utils.escape_html(String(d.allocated_percent)),
						])}</div>
						<div class="nsal-notice__b">${
							over
								? __("More is promised than there is to give.")
								: __("{0} is not assigned to anyone.", [
										format_currency(d.unallocated, frappe.defaults.get_default("currency")),
								  ])
						} ${__("Fix this in Narjes Settings → Revenue & Salaries.")}</div>
					</div>
					<button class="nsal-btn" data-route-settings
						onclick="frappe.set_route('Form','Narjes Settings')">${__("Open Settings")}</button>
				</div>`;
		}

		if (d.commission.stranded && d.commission.stranded.length) {
			// Commission counts by order date, revenue by invoice date. They
			// are the same day for a normal order, and only diverge on a
			// backdated one — where this month pays commission out of income
			// that landed in another month.
			const list = d.commission.stranded
				.slice(0, 5)
				.map(
					(x) =>
						`${frappe.utils.escape_html(x.sales_order)} (${__("ordered")} ${
							x.ordered
						}, ${__("invoiced")} ${x.invoiced})`
				)
				.join(", ");
			html += `
				<div class="nsal-notice nsal-notice--warn">
					<div>
						<div class="nsal-notice__t">${__(
							"{0} order(s) earned commission this month but were invoiced in another",
							[d.commission.stranded.length]
						)}</div>
						<div class="nsal-notice__b">${list}. ${__(
							"The commission is counted here because that is when the pieces were sold, but the income is counted in the month it reached the books — so the two months will not balance against each other."
						)}</div>
					</div>
				</div>`;
		}

		if (d.commission.skipped && d.commission.skipped.length) {
			// Never silently dropped: an item that should be earning
			// commission and is not is a pay dispute waiting to happen.
			const list = d.commission.skipped
				.map((s) => `${frappe.utils.escape_html(s.item_code)} (${frappe.utils.escape_html(s.reason)})`)
				.join(", ");
			html += `
				<div class="nsal-notice nsal-notice--warn">
					<div>
						<div class="nsal-notice__t">${__("Some pieces could not be counted")}</div>
						<div class="nsal-notice__b">${list}. ${__(
							"Commission is paid per piece, so anything sold by length is left out."
						)}</div>
					</div>
				</div>`;
		}

		return html;
	}

	cards(d, money) {
		return `
			<div class="nsal-cards">
				<div class="nsal-card nsal-card--profit">
					<div class="nsal-card__lbl">${__("Net profit to divide")}</div>
					<div class="nsal-card__val">${money(d.net_profit)}</div>
					<div class="nsal-card__sub">${__("from {0} taken in", [money(d.money_in)])}</div>
				</div>
				<div class="nsal-card nsal-card--people">
					<div class="nsal-card__lbl">${__("Paid to people")}</div>
					<div class="nsal-card__val">${money(d.paid_to_people)}</div>
					<div class="nsal-card__sub">${__("partners and commission")}</div>
				</div>
				<div class="nsal-card nsal-card--kept">
					<div class="nsal-card__lbl">${__("Kept in the business")}</div>
					<div class="nsal-card__val">${money(d.kept_in_business)}</div>
					<div class="nsal-card__sub">${__("emergencies and growth")}</div>
				</div>
			</div>`;
	}

	allocbar(d) {
		const palette = ["#9B3B3B", "#C8842A", "#2E5C46", "#5E8F77", "#8DB6A2", "#B5D0C2"];
		const parts = d.allocations
			.filter((a) => a.percent > 0)
			.map(
				(a, i) =>
					`<span style="width:${a.percent}%;background:${palette[i % palette.length]}"
						title="${frappe.utils.escape_html(a.label)} — ${a.percent}%">${a.percent}%</span>`
			)
			.join("");
		return parts ? `<div class="nsal-allocbar" role="img"
			aria-label="${__("How net profit is divided")}">${parts}</div>` : "";
	}

	person(p, prev, money) {
		const before = prev && (prev.allocations.find((a) => a.label === p.label) || {}).amount;
		return `
			<div class="nsal-person">
				<div class="nsal-person__av">${frappe.utils.escape_html((p.label || "?").trim().charAt(0))}</div>
				<div class="nsal-person__who">
					<div class="nsal-person__nm">${frappe.utils.escape_html(p.label)}</div>
					<div class="nsal-person__rl">${__("{0}% of net profit", [p.percent])}</div>
				</div>
				<div>
					<div class="nsal-person__amt">${money(p.amount)}</div>
					${this.delta(p.amount, before, money)}
				</div>
			</div>`;
	}

	commission_person(d, prev, money) {
		const c = d.commission;
		if (!c.total && !c.pieces) return "";
		const before = prev && prev.commission;
		return `
			<div class="nsal-person">
				<div class="nsal-person__av" style="background:var(--n-accent,#C8842A);color:#3A2A0C">
					${frappe.utils.escape_html((c.person || "W").trim().charAt(0))}</div>
				<div class="nsal-person__who">
					<div class="nsal-person__nm">${frappe.utils.escape_html(c.person || __("Walaa"))}</div>
					<div class="nsal-person__rl">${__("{0} pieces × {1} — paid as an expense", [
						c.pieces,
						money(c.rate),
					])}${c.posted ? "" : ` · <b>${__("not recorded yet")}</b>`}</div>
				</div>
				<div>
					<div class="nsal-person__amt">${money(c.total)}</div>
					${this.delta(c.total, before, money)}
				</div>
			</div>`;
	}

	delta(now, before, money) {
		if (before === undefined || before === null) {
			return `<div class="nsal-person__dl nsal-flat">${__("no month before")}</div>`;
		}
		const diff = now - before;
		if (Math.abs(diff) < 0.5) {
			return `<div class="nsal-person__dl nsal-flat">${__("same as last month")}</div>`;
		}
		const pct = before ? Math.abs((diff / Math.abs(before)) * 100) : null;
		const cls = diff > 0 ? "nsal-up" : "nsal-down";
		const arrow = diff > 0 ? "↑" : "↓";
		const tail = pct === null ? "" : ` · ${pct.toFixed(1)}%`;
		return `<div class="nsal-person__dl ${cls}">${arrow} ${money(Math.abs(diff))}${tail}</div>`;
	}

	fund(f, money) {
		const cls = /emerg/i.test(f.key) ? "nsal-box--emg" : "nsal-box--grw";
		return `
			<div class="nsal-box ${cls}">
				<div class="nsal-card__lbl">${frappe.utils.escape_html(f.label)}</div>
				<div class="nsal-box__val">${money(f.amount)}</div>
				<div class="nsal-card__sub">${f.percent}%</div>
			</div>`;
	}

	commission_breakdown(d, money) {
		const kinds = d.commission.by_kind || [];
		if (!kinds.length) {
			return `
				<div class="nsal-eyebrow" style="margin-top:18px">${__("Pieces sold")}</div>
				<div class="nsal-tablewrap"><div style="padding:16px;color:var(--n-text-3)">
					${__("No MDF, frames or stands were sold this month.")}
				</div></div>`;
		}
		const total = kinds.reduce((a, k) => a + k.amount, 0);
		const qty = kinds.reduce((a, k) => a + k.qty, 0);
		return `
			<div class="nsal-eyebrow" style="margin-top:18px">${__("What the commission was for")}</div>
			<div class="nsal-tablewrap">
				<table class="nsal-table" style="min-width:280px">
					<thead><tr>
						<th>${__("Piece")}</th><th class="nsal-num">${__("Sold")}</th>
						<th class="nsal-num">${__("Earns")}</th>
					</tr></thead>
					<tbody>${kinds
						.map(
							(k) => `<tr><td>${frappe.utils.escape_html(k.kind)}</td>
								<td class="nsal-num">${k.qty}</td>
								<td class="nsal-num">${money(k.amount)}</td></tr>`
						)
						.join("")}</tbody>
					<tfoot><tr><td>${__("Total")}</td>
						<td class="nsal-num">${qty}</td>
						<td class="nsal-num">${money(total)}</td></tr></tfoot>
				</table>
			</div>`;
	}

	history(data, money) {
		const rows = data.history;
		if (!rows.length) return "";

		// Column per person, built from whoever is actually configured —
		// never a fixed Ibrahim/Haneen pair, which would silently drop a
		// third partner if one were ever added.
		const names = [];
		rows.forEach((r) =>
			r.allocations.forEach((a) => {
				if (!names.includes(a.label)) names.push(a.label);
			})
		);

		const head = names.map((n) => `<th class="nsal-num">${frappe.utils.escape_html(n)}</th>`).join("");
		const body = rows
			.map((r) => {
				const cells = names
					.map((n) => {
						const a = r.allocations.find((x) => x.label === n);
						return `<td class="nsal-num">${a ? money(a.amount) : "—"}</td>`;
					})
					.join("");
				const change =
					r.change === null || r.change === undefined
						? `<td class="nsal-num nsal-flat">—</td>`
						: `<td class="nsal-num ${r.change >= 0 ? "nsal-up" : "nsal-down"}">${
								r.change >= 0 ? "↑" : "↓"
						  } ${
								r.change_percent === null || r.change_percent === undefined
									? money(Math.abs(r.change))
									: Math.abs(r.change_percent).toFixed(1) + "%"
						  }</td>`;
				return `<tr class="${r.month === data.month ? "is-current" : ""}">
					<td>${frappe.utils.escape_html(r.label)}</td>
					<td class="nsal-num">${money(r.net_profit)}</td>
					${cells}
					<td class="nsal-num">${money(r.commission)}</td>
					${change}
				</tr>`;
			})
			.join("");

		return `
			<div class="nsal-tablewrap">
				<table class="nsal-table">
					<thead><tr>
						<th>${__("Month")}</th>
						<th class="nsal-num">${__("Net profit")}</th>
						${head}
						<th class="nsal-num">${__("Commission")}</th>
						<th class="nsal-num">${__("Change")}</th>
					</tr></thead>
					<tbody>${body}</tbody>
				</table>
			</div>`;
	}

	// ------------------------------------------------------------ actions

	async post_commission(e) {
		const $btn = $(e.currentTarget);
		// Disabled immediately, with its own label, so a double-click cannot
		// even attempt a second posting — the server refuses one anyway, but
		// the button should not look like it is doing nothing either.
		$btn.prop("disabled", true).text(__("Recording…"));
		try {
			const r = await frappe.call({
				method: "narjes_custom.salaries.post_commission_expense",
				args: { month: this.month },
			});
			frappe.show_alert({ message: r.message.message, indicator: r.message.created ? "green" : "orange" });
			this.cache.clear(); // the ledger moved; every cached month may be stale
			await this.load();
		} catch (err) {
			$btn.prop("disabled", false).text(__("Try again"));
		}
	}
}
