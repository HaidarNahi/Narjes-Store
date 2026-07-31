// Narjes storefront client (plan W1/W7).
//
// Deliberately framework-free: adding Alpine/Vue would mean new npm packages,
// and the production image can only be rebuilt by a --no-cache Docker build
// that saturates the 1-vCPU VPS. Everything here is small, dependency-free,
// and progressive — the pages render and are navigable with JS disabled.

import { initTilt } from "./tilt";

const CART_KEY = "narjes.cart.v1";
const FAV_KEY = "narjes.favorites.v1";
const THEME_KEY = "narjes.theme";

/* ------------------------------------------------------------------ store */
// Cart and favourites live in localStorage: there are no accounts in v1, so
// there is nowhere on the server to hang them. The server re-validates every
// line at checkout, so a tampered cart can never set its own prices.

const read = (key, fallback) => {
	try {
		return JSON.parse(localStorage.getItem(key)) ?? fallback;
	} catch {
		return fallback;
	}
};
const write = (key, value) => {
	try {
		localStorage.setItem(key, JSON.stringify(value));
	} catch {
		/* private mode / quota — the UI still works for this page view */
	}
};

export const cart = {
	all: () => read(CART_KEY, []),
	count: () => cart.all().reduce((n, l) => n + l.qty, 0),
	add(item_code, qty = 1, meta = {}) {
		const lines = cart.all();
		const line = lines.find((l) => l.item_code === item_code);
		if (line) line.qty += qty;
		else lines.push({ item_code, qty, ...meta });
		write(CART_KEY, lines);
		sync();
		return lines;
	},
	setQty(item_code, qty) {
		let lines = cart.all();
		lines = qty <= 0
			? lines.filter((l) => l.item_code !== item_code)
			: lines.map((l) => (l.item_code === item_code ? { ...l, qty } : l));
		write(CART_KEY, lines);
		sync();
		return lines;
	},
	remove: (item_code) => cart.setQty(item_code, 0),
	clear() {
		write(CART_KEY, []);
		sync();
	},
};

export const favorites = {
	all: () => read(FAV_KEY, []),
	has: (item_code) => favorites.all().includes(item_code),
	toggle(item_code) {
		const list = favorites.all();
		const i = list.indexOf(item_code);
		if (i === -1) list.push(item_code);
		else list.splice(i, 1);
		write(FAV_KEY, list);
		sync();
		return i === -1;
	},
};

function sync() {
	const badge = (sel, n) => {
		document.querySelectorAll(sel).forEach((el) => {
			el.textContent = n > 99 ? "99+" : String(n);
			el.classList.toggle("is-on", n > 0);
		});
	};
	badge("[data-cart-count]", cart.count());
	badge("[data-fav-count]", favorites.all().length);
	document.querySelectorAll("[data-fav-toggle]").forEach((btn) => {
		btn.setAttribute("aria-pressed", String(favorites.has(btn.dataset.favToggle)));
	});
	document.dispatchEvent(new CustomEvent("narjes:store-changed"));
}

/* ------------------------------------------------------------------ theme */

function initTheme() {
	// Light is the shop's chosen default. The OS preference is deliberately
	// NOT consulted: the brand's photography and palette are built around
	// Paper, so a visitor whose laptop happens to be in dark mode should still
	// meet the store the way it was designed. Dark remains one tap away and is
	// remembered once chosen.
	const saved = localStorage.getItem(THEME_KEY);
	apply(saved === "dark" || saved === "light" ? saved : "light");

	document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
		btn.addEventListener("click", () => {
			const next =
				document.documentElement.getAttribute("data-theme") === "dark"
					? "light"
					: "dark";
			apply(next);
			localStorage.setItem(THEME_KEY, next);
		});
	});

	function apply(mode) {
		document.documentElement.setAttribute("data-theme", mode);
		document.querySelectorAll("[data-theme-toggle]").forEach((b) =>
			b.setAttribute("aria-label", mode === "dark" ? "Light mode" : "Dark mode")
		);
	}
}

/* ----------------------------------------------------------------- loader */

function initLoader() {
	const loader = document.querySelector(".s-loader");
	if (!loader) return;
	const done = () => loader.classList.add("is-done");
	// never let the loader outlive the content it covers
	if (document.readyState === "complete") setTimeout(done, 380);
	else window.addEventListener("load", () => setTimeout(done, 380));
	setTimeout(done, 2600);
}

/* ---------------------------------------------------------------- reveals */

function initReveals() {
	const targets = document.querySelectorAll("[data-reveal], [data-reveal-group]");
	if (!targets.length) return;
	if (!("IntersectionObserver" in window)) {
		targets.forEach((t) => t.classList.add("is-in"));
		return;
	}
	const io = new IntersectionObserver(
		(entries) => {
			entries.forEach((e) => {
				if (e.isIntersecting) {
					e.target.classList.add("is-in");
					io.unobserve(e.target);
				}
			});
		},
		{ rootMargin: "0px 0px -8% 0px", threshold: 0.06 }
	);
	targets.forEach((t) => io.observe(t));
}

/* ----------------------------------------------------------------- toasts */

export function toast(message, icon = "check-circle") {
	let host = document.querySelector(".s-toasts");
	if (!host) {
		host = document.createElement("div");
		host.className = "s-toasts";
		document.body.appendChild(host);
	}
	const el = document.createElement("div");
	el.className = "s-toast";
	el.setAttribute("role", "status");
	el.innerHTML =
		`<svg aria-hidden="true"><use href="#ph-${icon}"></use></svg><span></span>`;
	el.querySelector("span").textContent = message;
	host.appendChild(el);
	setTimeout(() => {
		el.style.transition = "opacity 300ms, transform 300ms";
		el.style.opacity = "0";
		el.style.transform = "translateY(6px)";
		setTimeout(() => el.remove(), 320);
	}, 2600);
}

/* ------------------------------------------------------- add-to-cart flight */

function fly(fromEl) {
	const target = document.querySelector("[data-cart-open]");
	const img = fromEl?.closest("[data-product-card], .s-product")?.querySelector("img");
	if (!target || !img || window.matchMedia("(prefers-reduced-motion: reduce)").matches)
		return;

	const a = img.getBoundingClientRect();
	const b = target.getBoundingClientRect();
	const ghost = img.cloneNode();
	ghost.className = "s-fly";
	Object.assign(ghost.style, {
		left: `${a.left}px`,
		top: `${a.top}px`,
		width: `${a.width}px`,
		height: `${a.height}px`,
	});
	document.body.appendChild(ghost);
	requestAnimationFrame(() => {
		const dx = b.left + b.width / 2 - (a.left + a.width / 2);
		const dy = b.top + b.height / 2 - (a.top + a.height / 2);
		ghost.style.transform = `translate(${dx}px, ${dy}px) scale(0.12)`;
		ghost.style.opacity = "0.15";
	});
	setTimeout(() => ghost.remove(), 720);
}

/* ---------------------------------------------------------------- drawers */

function initDrawers() {
	const scrim = document.querySelector(".s-scrim");
	const close = () => {
		document.querySelectorAll(".s-drawer.is-open").forEach((d) => d.classList.remove("is-open"));
		scrim?.classList.remove("is-open");
		document.body.style.overflow = "";
	};
	const open = (sel) => {
		const d = document.querySelector(sel);
		if (!d) return;
		d.classList.add("is-open");
		scrim?.classList.add("is-open");
		document.body.style.overflow = "hidden";
		d.querySelector("button, a, input")?.focus();
	};

	document.addEventListener("click", (e) => {
		const opener = e.target.closest("[data-drawer-open]");
		if (opener) {
			e.preventDefault();
			open(opener.dataset.drawerOpen);
		}
		if (e.target.closest("[data-drawer-close]")) close();
	});
	scrim?.addEventListener("click", close);
	document.addEventListener("keydown", (e) => e.key === "Escape" && close());
}

/* ------------------------------------------------------------- delegation */

function initActions() {
	document.addEventListener("click", (e) => {
		const add = e.target.closest("[data-add-to-cart]");
		if (add) {
			e.preventDefault();
			const qtyInput = document.querySelector("[data-qty-input]");
			const qty = add.dataset.qty
				? Number(add.dataset.qty)
				: qtyInput
					? Math.max(1, Number(qtyInput.value) || 1)
					: 1;
			cart.add(add.dataset.addToCart, qty, {
				name: add.dataset.name || "",
				rate: Number(add.dataset.rate) || 0,
				image: add.dataset.image || "",
				route: add.dataset.route || "",
			});
			fly(add);
			toast(add.dataset.added || "Added to cart", "check-circle");
		}

		const fav = e.target.closest("[data-fav-toggle]");
		if (fav) {
			e.preventDefault();
			const on = favorites.toggle(fav.dataset.favToggle);
			toast(
				on
					? fav.dataset.favOn || "Saved to favourites"
					: fav.dataset.favOff || "Removed from favourites",
				"heart"
			);
		}

		const step = e.target.closest("[data-qty-step]");
		if (step) {
			e.preventDefault();
			const input = step.parentElement.querySelector("input");
			if (input) {
				const next = Math.max(1, (Number(input.value) || 1) + Number(step.dataset.qtyStep));
				input.value = next;
				input.dispatchEvent(new Event("change", { bubbles: true }));
			}
		}
	});
}

/* -------------------------------------------------------------------- init */

function boot() {
	initTheme();
	initLoader();
	initReveals();
	initDrawers();
	initActions();
	initTilt();
	sync();
}

if (document.readyState === "loading") {
	document.addEventListener("DOMContentLoaded", boot);
} else {
	boot();
}

window.narjesShop = { cart, favorites, toast };
