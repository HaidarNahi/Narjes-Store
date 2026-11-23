"""
narjes_custom.ai_intake.order_type
==================================
The order's occasion — Sales Order.design_type, labelled "Order Type"
(حج، عمره، تخرج، اعراس، اطفال).

The AI is asked for it first (constrained to the field's options by the
response schema). This module then

* normalises what the AI returned onto a real option — "عمرة" is "عمره",
  "زواج" is "اعراس" — because a Select rejects anything else, and
* reads the message itself when the AI left it empty, by whole words, so a
  message that plainly says "تخرج" never reaches the reviewer blank.

Whole words, not substrings: "حج" is inside "حجم" (size), which appears on
almost every order. And a word that could mean two occasions settles nothing:
"طفل عمره سنتين" says *kids*, not *Umrah* ("عمره" is also "his age"), so when
the words point at more than one type the answer is left to the reviewer.

Pure functions only — no Frappe import — so the tests run without a site.
"""

import re
import unicodedata

# Words that mean each occasion, written the way customers write them.
# Keyed by the option text in custom_fields; an option added there without
# synonyms here still matches its own spelling.
SYNONYMS = {
	"حج": ("حج", "الحج", "حجاج", "الحجاج", "حاج", "الحاج", "حاجه", "حجي", "حجيه"),
	"عمره": ("عمره", "العمره", "معتمر", "معتمره", "المعتمر"),
	"تخرج": ("تخرج", "التخرج", "تخرجي", "تخرجه", "خريج", "خريجه", "الخريج", "الخريجه", "graduation"),
	"اعراس": (
		"اعراس",
		"الاعراس",
		"عرس",
		"العرس",
		"زواج",
		"الزواج",
		"زفاف",
		"الزفاف",
		"عروس",
		"العروس",
		"عرسان",
		"العرسان",
		"عريس",
		"العريس",
		"خطوبه",
		"الخطوبه",
		"ملكه",
		"الملكه",
		"ملچه",
		"wedding",
	),
	"اطفال": (
		"اطفال",
		"الاطفال",
		"طفل",
		"الطفل",
		"طفله",
		"الطفله",
		"مولود",
		"المولود",
		"مولوده",
		"مواليد",
		"المواليد",
		"بيبي",
		"baby",
		"kids",
	),
}

# A word that names one occasion but is also an everyday word elsewhere: it
# only counts when nothing else in the message points at a different type.
WEAK = {"عمره"}

_DIACRITICS = re.compile(r"[ً-ٰٟـ]")  # harakat, dagger alif, tatweel
_WORD = re.compile(r"[\w؀-ۿ]+")


def _norm(text) -> str:
	"""Fold the spellings Arabic keyboards mix: أإآ→ا, ة→ه, ى→ي, no harakat."""
	text = unicodedata.normalize("NFKC", str(text or "")).lower()
	text = _DIACRITICS.sub("", text)
	return text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"}))


def _lookup(options) -> dict:
	"""normalised word -> option, for the options that really exist."""
	table = {}
	for option in options:
		option = (option or "").strip()
		if not option:
			continue
		key = _norm(option)
		table[key] = option
		for canonical, words in SYNONYMS.items():
			if _norm(canonical) == key:
				for word in words:
					table.setdefault(_norm(word), option)
	return table


def normalize(value, options) -> str:
	"""Map a value onto one of `options`, or "" when it isn't one."""
	value = _norm(value).strip()
	if not value:
		return ""
	table = _lookup(options)
	if value in table:
		return table[value]
	# "حفلة تخرج", "طلب اعراس": a short phrase naming exactly one type
	hits = {table[w] for w in _WORD.findall(value) if w in table}
	return hits.pop() if len(hits) == 1 else ""


def _strip_prefix(word) -> list:
	"""The word, plus it without a leading و/ب/ل/لل/ولل/وب/وال/بال ("وللتخرج").

	Shortest prefix first, so "والعمره" is tried as "العمره" (the Umrah,
	unambiguous) before the bare "عمره" (which may be "his age")."""
	out = [word]
	for prefix in ("و", "ب", "ل", "لل", "ولل", "وب", "وال", "بال"):
		if word.startswith(prefix) and len(word) - len(prefix) >= 2:
			out.append(word[len(prefix) :])
	return out


def detect(text, options) -> str:
	"""The single order type `text` names, or "" when none or several."""
	table = _lookup(options)
	strong, weak = set(), set()
	for word in _WORD.findall(_norm(text)):
		for candidate in _strip_prefix(word):
			option = table.get(candidate)
			if option:
				(weak if candidate in WEAK else strong).add(option)
				break
	if len(strong) == 1:
		return next(iter(strong))
	if not strong and len(weak) == 1:
		return next(iter(weak))
	return ""


def resolve(ai_value, raw_text, options) -> str:
	"""The AI's answer when it is a real option, else what the message says."""
	return normalize(ai_value, options) or detect(raw_text, options)


def options_from(select_options) -> list:
	"""A Select field's options string as a list, blank line dropped."""
	return [o.strip() for o in (select_options or "").split("\n") if o.strip()]
