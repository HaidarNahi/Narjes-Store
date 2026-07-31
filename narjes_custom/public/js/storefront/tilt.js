/* Cursor-following 3D tilt for the hero artwork.
 *
 * Smoothness rules this obeys, because "no lag or glitching" is the whole
 * point of the effect:
 *
 *  - pointermove only records coordinates. All geometry and DOM writes happen
 *    in one requestAnimationFrame loop, so a fast mouse can never queue up more
 *    work than the display can draw.
 *  - getBoundingClientRect() is never called from the pointer handler. It is
 *    cached and refreshed on resize/scroll, so moving the mouse can't force a
 *    layout (the classic cause of tilt-effect jank).
 *  - The current angle eases toward the target instead of snapping to it, which
 *    removes the stutter you get from mapping raw pointer deltas.
 *  - The rAF loop stops once the frame has settled and restarts on the next
 *    interaction, so an idle page burns nothing.
 *  - Only transform and opacity change — no layout, no paint.
 */

const MAX_TILT = 11; // degrees
const HOVER_LIFT = 16; // px toward the viewer
const EASE = 0.12; // approach rate per frame
const SETTLED = 0.01;

export function initTilt() {
	const stage = document.querySelector("[data-tilt]");
	if (!stage) return;

	const frame = stage.querySelector(".s-tilt-frame");
	const gloss = stage.querySelector(".s-tilt-gloss");
	if (!frame) return;

	// Pointer tilt is meaningless without a pointer, and unwanted when the
	// visitor has asked for reduced motion.
	const fine = window.matchMedia("(pointer: fine)");
	const calm = window.matchMedia("(prefers-reduced-motion: reduce)");
	if (!fine.matches || calm.matches) return;

	let rect = null;
	let raf = 0;
	let running = false;

	// target vs current, eased each frame
	let tx = 0, ty = 0, tz = 0, tg = 0;
	let cx = 0, cy = 0, cz = 0, cg = 0;
	// last pointer position, in stage-local ratios
	let px = 0.5, py = 0.5;

	const measure = () => { rect = stage.getBoundingClientRect(); };

	function onMove(event) {
		if (!rect) measure();
		// pure arithmetic — no DOM reads on the hot path
		const nx = (event.clientX - rect.left) / rect.width;
		const ny = (event.clientY - rect.top) / rect.height;
		px = Math.min(Math.max(nx, 0), 1);
		py = Math.min(Math.max(ny, 0), 1);
		ty = (px - 0.5) * 2 * MAX_TILT;      // rotateY follows horizontal
		tx = (0.5 - py) * 2 * MAX_TILT;      // rotateX follows vertical
		start();
	}

	function onEnter() {
		measure();
		tz = HOVER_LIFT;
		tg = 1;
		stage.classList.add("is-live");
		start();
	}

	function onLeave() {
		tx = ty = tz = 0;
		tg = 0;
		stage.classList.remove("is-live");
		start();
	}

	function frameStep() {
		cx += (tx - cx) * EASE;
		cy += (ty - cy) * EASE;
		cz += (tz - cz) * EASE;
		cg += (tg - cg) * EASE;

		frame.style.transform =
			`rotateX(${cx.toFixed(3)}deg) rotateY(${cy.toFixed(3)}deg) ` +
			`translateZ(${cz.toFixed(2)}px) scale(${(1 + cz / 900).toFixed(4)})`;

		if (gloss && cg > 0.001) {
			gloss.style.setProperty("--gloss-x", `${(px * 100).toFixed(1)}%`);
			gloss.style.setProperty("--gloss-y", `${(py * 100).toFixed(1)}%`);
		}

		const settled =
			Math.abs(tx - cx) < SETTLED && Math.abs(ty - cy) < SETTLED &&
			Math.abs(tz - cz) < SETTLED && Math.abs(tg - cg) < SETTLED;

		if (settled) {
			// snap the residue away and let the loop idle
			frame.style.transform =
				`rotateX(${tx}deg) rotateY(${ty}deg) translateZ(${tz}px) scale(${1 + tz / 900})`;
			running = false;
			return;
		}
		raf = requestAnimationFrame(frameStep);
	}

	function start() {
		if (running) return;
		running = true;
		raf = requestAnimationFrame(frameStep);
	}

	stage.addEventListener("pointerenter", onEnter);
	stage.addEventListener("pointermove", onMove, { passive: true });
	stage.addEventListener("pointerleave", onLeave);

	// Geometry only ever re-read when it can actually have changed.
	addEventListener("resize", measure, { passive: true });
	addEventListener("scroll", measure, { passive: true });

	// If the visitor turns reduced motion on mid-session, stop immediately.
	calm.addEventListener("change", (e) => {
		if (e.matches) {
			cancelAnimationFrame(raf);
			running = false;
			frame.style.transform = "";
			stage.classList.remove("is-live");
		}
	});
}
