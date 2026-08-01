/* Product gallery: thumbnails, hover zoom, and a lightbox previewer.
 *
 * The zoom follows the same rules as the hero tilt — pointer handlers only
 * record coordinates, geometry is cached rather than measured per move, and
 * only background-position/transform change, so it stays smooth on a phone.
 */

const ZOOM = 2.4;

export function initGallery() {
	initThumbs();
	initZoom();
	initLightbox();
}

/* ------------------------------------------------------------- thumbnails */

function initThumbs() {
	const main = document.getElementById("s-main-img");
	const thumbs = document.querySelectorAll("[data-thumb]");
	if (!main || !thumbs.length) return;

	thumbs.forEach((btn) => {
		btn.addEventListener("click", () => {
			const src = btn.querySelector("img")?.src;
			if (!src) return;
			main.src = src;
			// the zoom layer must follow the swap, not keep the old shot
			const stage = main.closest("[data-zoom]");
			if (stage) stage.style.backgroundImage = `url("${src}")`;
			thumbs.forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
		});
	});
}

/* ------------------------------------------------------------- hover zoom */

function initZoom() {
	const stage = document.querySelector("[data-zoom]");
	const img = stage?.querySelector("img");
	if (!stage || !img) return;

	// Pointer zoom needs a pointer. On touch the lightbox (with pinch-zoom)
	// is the right affordance, so this is skipped entirely there.
	if (!window.matchMedia("(pointer: fine)").matches) return;

	let rect = null;
	let raf = 0;
	let pending = null;

	const measure = () => { rect = stage.getBoundingClientRect(); };
	const load = () => { stage.style.backgroundImage = `url("${img.currentSrc || img.src}")`; };

	if (img.complete) load();
	else img.addEventListener("load", load, { once: true });

	stage.addEventListener("pointerenter", () => {
		measure();
		load();
		stage.classList.add("is-zooming");
	});

	stage.addEventListener("pointermove", (e) => {
		if (!rect) measure();
		pending = e;
		if (raf) return;
		raf = requestAnimationFrame(() => {
			raf = 0;
			const x = ((pending.clientX - rect.left) / rect.width) * 100;
			const y = ((pending.clientY - rect.top) / rect.height) * 100;
			const cx = Math.min(Math.max(x, 0), 100);
			const cy = Math.min(Math.max(y, 0), 100);
			stage.style.backgroundPosition = `${cx}% ${cy}%`;
			stage.style.setProperty("--lens-x", `${cx}%`);
			stage.style.setProperty("--lens-y", `${cy}%`);
		});
	}, { passive: true });

	stage.addEventListener("pointerleave", () => {
		stage.classList.remove("is-zooming");
		if (raf) { cancelAnimationFrame(raf); raf = 0; }
	});

	stage.style.backgroundSize = `${ZOOM * 100}%`;
	addEventListener("resize", measure, { passive: true });
	addEventListener("scroll", measure, { passive: true });
}

/* -------------------------------------------------------------- lightbox */

function initLightbox() {
	const stage = document.querySelector("[data-lightbox]");
	if (!stage) return;

	const shots = [...document.querySelectorAll("[data-thumb] img")].map((i) => i.src);
	const main = document.getElementById("s-main-img");
	const all = shots.length ? shots : [main?.src].filter(Boolean);
	let index = 0;
	let box = null;

	function build() {
		box = document.createElement("div");
		box.className = "s-lightbox";
		box.setAttribute("role", "dialog");
		box.setAttribute("aria-modal", "true");
		box.innerHTML =
			'<button class="s-lb-close" aria-label="Close"><svg aria-hidden="true"><use href="#ph-x"></use></svg></button>' +
			(all.length > 1
				? '<button class="s-lb-nav s-lb-prev" aria-label="Previous"><svg aria-hidden="true"><use href="#ph-caret-left"></use></svg></button>' +
				  '<button class="s-lb-nav s-lb-next" aria-label="Next"><svg aria-hidden="true"><use href="#ph-caret-right"></use></svg></button>'
				: "") +
			'<figure class="s-lb-stage"><img alt=""></figure>';
		document.body.appendChild(box);

		box.addEventListener("click", (e) => {
			if (e.target === box || e.target.closest(".s-lb-close")) close();
			if (e.target.closest(".s-lb-prev")) step(-1);
			if (e.target.closest(".s-lb-next")) step(1);
		});
	}

	function show() {
		box.querySelector("img").src = all[index];
	}

	function step(delta) {
		index = (index + delta + all.length) % all.length;
		show();
	}

	function open(from) {
		if (!box) build();
		index = Math.max(all.indexOf(from), 0);
		show();
		box.classList.add("is-open");
		document.body.style.overflow = "hidden";
		box.querySelector(".s-lb-close").focus();
		document.addEventListener("keydown", onKey);
	}

	function close() {
		box.classList.remove("is-open");
		document.body.style.overflow = "";
		document.removeEventListener("keydown", onKey);
	}

	function onKey(e) {
		if (e.key === "Escape") close();
		if (e.key === "ArrowRight") step(1);
		if (e.key === "ArrowLeft") step(-1);
	}

	stage.addEventListener("click", (e) => {
		// the zoom button and the image both open it
		if (e.target.closest(".s-zoom-open") || e.target.tagName === "IMG") {
			open(main?.currentSrc || main?.src);
		}
	});
}
