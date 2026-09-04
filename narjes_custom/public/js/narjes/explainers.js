// Plain-language explainers for the numbers in reports and dashboards.
//
// Staff read "Gross profit" and reasonably wonder whether it is before or after
// the ads, and where the figure came from. Every explained number gets a small
// button beside its label opening a note in two parts: what it means, and how
// it was worked out.
//
// The words themselves live in Python, next to the code that does the sum —
// see narjes_custom/reports_meta.py. Anything that changes how a number is
// calculated is then sitting next to the sentence describing it, which is the
// only arrangement that stays true a year later.
//
// SHIM: wraps frappe.utils.build_summary_item (see docs/SHIM_REGISTRY.md #6).
// The wrap is additive — the original builds the card, this appends a button to
// it — so a report that ships no explanations is untouched.

const ICON = "info";

function icon_markup() {
	// Same sprite as every other icon in the theme. Frappe's own set is Lucide;
	// mixing the two families in one row is visible.
	return (
		'<svg class="icon narjes-explain__icon" aria-hidden="true">' +
		`<use href="#ph-${ICON}"></use>` +
		"</svg>"
	);
}

let seq = 0;

/**
 * The button + its popup, ready to drop next to a label.
 *
 * @param {Object} spec
 * @param {string} spec.title    what is being explained
 * @param {string} spec.what     one plain sentence
 * @param {string} [spec.how]    how the figure is worked out
 * @returns {jQuery} a <span> holding the button and the popup
 */
export function explainer(spec) {
	if (!spec || !spec.what) return null;

	const id = `narjes-explain-${++seq}`;
	const label = __("What is {0}?", [spec.title || ""]);

	const $wrap = $(`
		<span class="narjes-explain">
			<button type="button" class="narjes-explain__btn"
				aria-expanded="false" aria-controls="${id}"
				aria-label="${frappe.utils.escape_html(label)}">${icon_markup()}</button>
			<span class="narjes-explain__pop" id="${id}" role="dialog" hidden
				aria-label="${frappe.utils.escape_html(spec.title || "")}">
				<span class="narjes-explain__title"></span>
				<span class="narjes-explain__what"></span>
			</span>
		</span>
	`);

	// textContent, not interpolation: these strings are translated and could
	// one day come from a settings field, and a report label is not a place to
	// start trusting HTML.
	$wrap.find(".narjes-explain__title").text(spec.title || "");
	$wrap.find(".narjes-explain__what").text(spec.what);

	if (spec.how) {
		const $how = $(
			'<span class="narjes-explain__how">' +
				`<span class="narjes-explain__how-label">${__("How it is worked out")}</span>` +
				'<span class="narjes-explain__how-value"></span>' +
				"</span>"
		);
		$how.find(".narjes-explain__how-value").text(spec.how);
		$wrap.find(".narjes-explain__pop").append($how);
	}

	const $pop = $wrap.find(".narjes-explain__pop");
	$pop.data("home", $wrap);
	$wrap.data("pop", $pop);

	$wrap.find(".narjes-explain__btn").on("click", (e) => {
		e.preventDefault();
		e.stopPropagation();
		toggle($wrap);
	});

	return $wrap;
}

// The open popup, moved to <body> for as long as it is open. See place().
let $open_pop = null;
let $open_btn = null;

function toggle($wrap) {
	const $btn = $wrap.find(".narjes-explain__btn");
	const open = $btn.attr("aria-expanded") === "true";

	close_all();
	if (open) return;

	const $pop = $wrap.data("pop");

	// Rendered on <body>, not in place. Frappe sets `overflow: hidden
	// !important` on .summary-label, which is 21px tall — a note anchored
	// inside it is simply never drawn, and no amount of specificity beats an
	// !important. Overriding it would also switch off label truncation for
	// every report in the desk, to fix a popup. Taking the popup out of the
	// flow instead leaves Frappe's behaviour exactly as it was, and makes this
	// immune to whatever the next container does.
	$("body").append($pop);
	$pop.prop("hidden", false);
	$btn.attr("aria-expanded", "true");

	$open_pop = $pop;
	$open_btn = $btn;
	place();
}

function place() {
	if (!$open_pop || !$open_btn) return;

	const anchor = $open_btn[0].getBoundingClientRect();
	const pop = $open_pop[0].getBoundingClientRect();
	const margin = 12;

	// Centred under the button, then pulled back inside the viewport — the
	// first and last cards in a summary row sit near the page edge.
	let left = anchor.left + anchor.width / 2 - pop.width / 2;
	left = Math.max(margin, Math.min(left, window.innerWidth - pop.width - margin));

	// Prefer below the button, flip above when there is no room, and if it fits
	// neither — a short window, or a tall note — clamp it into view rather than
	// letting it run off the edge. Something always has to be readable.
	const below = anchor.bottom + 10;
	const fits_below = below + pop.height <= window.innerHeight - margin;
	const fits_above = anchor.top - pop.height - 10 >= margin;
	const flip = !fits_below && fits_above;

	let top = flip ? anchor.top - pop.height - 10 : below;
	if (!fits_below && !fits_above) {
		top = Math.max(margin, window.innerHeight - pop.height - margin);
	}

	$open_pop
		.toggleClass("narjes-explain__pop--above", flip)
		.css({ left: `${Math.round(left)}px`, top: `${Math.round(top)}px` })
		// The little arrow tracks the button rather than the panel, since the
		// two are no longer centred on each other once the panel is nudged.
		.css("--arrow-x", `${Math.round(anchor.left + anchor.width / 2 - left)}px`);
}

function close_all() {
	if ($open_pop) {
		// Back to its own wrapper, so the button and its note stay one unit and
		// nothing is orphaned on <body> when the report re-renders.
		$open_pop.prop("hidden", true).removeClass("narjes-explain__pop--above").css({ left: "", top: "" });
		const $home = $open_pop.data("home");
		if ($home && $home.length) $home.append($open_pop);
	}
	$(".narjes-explain__btn").attr("aria-expanded", "false");
	$open_pop = null;
	$open_btn = null;
}

// One set of global handlers for every explainer on the page.
$(document).on("click", (e) => {
	if (!$(e.target).closest(".narjes-explain").length) close_all();
});
$(document).on("keydown", (e) => {
	if (e.key === "Escape") close_all();
});
// Fixed positioning does not follow the page, so re-anchor on anything that
// moves the button. Capture phase catches scrolling inside the report body,
// which does not bubble.
window.addEventListener("scroll", place, true);
window.addEventListener("resize", place);

/**
 * Attach explainers to a rendered query-report summary row.
 *
 * Called from each report's after_refresh. Frappe rebuilds the row on every
 * refresh, so this runs again each time; matching on the label keeps it
 * independent of card order.
 */
export function attach_to_report(report) {
	const summary = report?.raw_data?.report_summary;
	const $row = report?.$summary;
	if (!summary || !$row || !$row.length) return;

	$row.find(".summary-item").each(function (index) {
		const $item = $(this);
		if ($item.find(".narjes-explain").length) return; // already done

		const spec = summary[index];
		if (!spec || !spec.explanation) return;

		const $btn = explainer({
			title: __(spec.label),
			what: __(spec.explanation),
			how: spec.formula ? __(spec.formula) : "",
		});
		if ($btn) $item.find(".summary-label").append($btn);
	});
}

// ---------------------------------------------------------------- the shim

const original = frappe.utils.build_summary_item;

frappe.utils.build_summary_item = function (summary) {
	const $item = original.call(this, summary);

	// Only cards that ship an explanation are touched; everything else in the
	// desk keeps Frappe's exact markup.
	if (summary && summary.explanation) {
		const $btn = explainer({
			title: __(summary.label),
			what: __(summary.explanation),
			how: summary.formula ? __(summary.formula) : "",
		});
		if ($btn) $item.find(".summary-label").append($btn);
	}

	return $item;
};

// Page scripts (narjes_home, narjes_salaries, narjes_debts) are plain scripts
// rather than modules, so they reach it through the global.
window.narjes_explainer = explainer;
window.narjes_attach_explainers = attach_to_report;
