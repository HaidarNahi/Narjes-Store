// Narjes Ledger — upload defaults.
//
// Frappe ticks the "Optimize" checkbox by default for any image over 200 KB
// (FileUploader.vue, add_files). Optimising re-encodes and downscales the
// file, which is wrong for this business: the images attached to a Sales
// Order are the artwork that gets printed, and the print shop needs the
// original resolution, not a web-sized copy.
//
// The default cannot simply be passed in — it is computed inside frappe's
// bundled Vue component, and production builds clone frappe fresh from
// upstream, so editing frappe itself would never reach the server. Instead
// the box is unticked once per file preview, by dispatching the component's
// own change event. Going through the component keeps the checkbox and the
// underlying file.optimize in agreement, and because each preview is only
// touched once, a user who deliberately ticks Optimize still gets it.

const OPTIMIZE_LABEL = '[id="uploader-optimize-checkbox"]';
// Marks a checkbox as already defaulted, so re-ticking it by hand sticks.
const HANDLED_FLAG = "narjesOptimizeDefaulted";

function default_optimize_off(root) {
	if (!root || typeof root.querySelectorAll !== "function") return;

	root.querySelectorAll(OPTIMIZE_LABEL).forEach((label) => {
		const box = label.querySelector('input[type="checkbox"]');
		if (!box || box.dataset[HANDLED_FLAG]) return;

		box.dataset[HANDLED_FLAG] = "1";
		if (!box.checked) return;

		box.checked = false;
		// The Vue component listens for the native change event and flips
		// file.optimize itself — setting .checked alone would desync them.
		box.dispatchEvent(new Event("change", { bubbles: true }));
	});
}

function watch_for_upload_dialogs() {
	if (!document.body || window.__narjes_optimize_observer) return;

	const observer = new MutationObserver((mutations) => {
		for (const mutation of mutations) {
			for (const node of mutation.addedNodes) {
				if (node.nodeType !== Node.ELEMENT_NODE) continue;
				// Cheap bail-out: the checkbox only ever appears inside a
				// freshly rendered file preview.
				if (node.matches?.(OPTIMIZE_LABEL) || node.querySelector?.(OPTIMIZE_LABEL)) {
					default_optimize_off(node.matches?.(OPTIMIZE_LABEL) ? node.parentNode : node);
				}
			}
		}
	});

	observer.observe(document.body, { childList: true, subtree: true });
	window.__narjes_optimize_observer = observer;

	// Anything already on screen when this loads.
	default_optimize_off(document.body);
}

$(document).ready(watch_for_upload_dialogs);
