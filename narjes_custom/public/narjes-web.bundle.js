// Narjes Ledger — website/login JS: apply the theme class. The desk kill
// switch rides frappe.boot; website pages have no boot, so the class is
// unconditional here (the login reskin is pure CSS and reverts with the
// bundle include if ever needed).

document.addEventListener("DOMContentLoaded", () => {
	document.body.classList.add("narjes-ledger");
	if (
		document.querySelector(".login-content.page-card") ||
		window.location.pathname === "/login" ||
		window.location.pathname === "/update-password"
	) {
		document.body.classList.add("login-page");
	}
});
