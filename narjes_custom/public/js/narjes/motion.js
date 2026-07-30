// P11 — the motion catalog's JS half. One API (narjes.motion.*) so pages
// can't invent variants. Transform/opacity only; reduced-motion collapses
// everything (the CSS guard lives in _shame.scss, and count-up checks here).

const reduced = () =>
	window.matchMedia("(prefers-reduced-motion: reduce)").matches;

window.narjes = window.narjes || {};

window.narjes.motion = {
	// Stamp-down (the signature): terminal transitions + intake success only.
	stamp(el) {
		if (!el || reduced()) return;
		el.classList.remove("n-stamp--stamping");
		// restart the animation if it just ran
		void el.offsetWidth;
		el.classList.add("n-stamp--stamping");
	},

	// KPI count-up: once per page load, 600ms ease-out, no layout shift (tnum)
	countUp(el, value, { duration = 600, format = (v) => Math.round(v).toLocaleString() } = {}) {
		if (!el) return;
		if (reduced()) {
			el.textContent = format(value);
			return;
		}
		const start = performance.now();
		const from = 0;
		const tick = (now) => {
			const t = Math.min((now - start) / duration, 1);
			const eased = 1 - Math.pow(1 - t, 3);
			el.textContent = format(from + (value - from) * eased);
			if (t < 1) requestAnimationFrame(tick);
		};
		requestAnimationFrame(tick);
	},

	// Like-heart pop
	pop(el) {
		if (!el || reduced()) return;
		el.animate(
			[
				{ transform: "scale(1)" },
				{ transform: "scale(1.2)" },
				{ transform: "scale(1)" },
			],
			{ duration: 180, easing: "cubic-bezier(0.2, 0, 0, 1)" }
		);
	},
};
