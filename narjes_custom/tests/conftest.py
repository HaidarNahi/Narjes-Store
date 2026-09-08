"""Make this app's modules importable outside a running bench.

The unit suites here are deliberately site-free — they assert on pure
functions and on Frappe's own registries, never on a database — so they can
run in CI in a second without MariaDB, Redis or a site.

Importing them still drags in `frappe`, and `frappe` configures a rotating
file logger the moment something in its web/email stack (cssutils, via the
website modules the storefront imports) is touched. That logger resolves its
path relative to the *bench* directory, two levels above this app. Run pytest
from the app directory — which is what CI does, and what anyone in this repo
would type — and it tries to open `apps/logs/cssutils.log`, a directory that
does not exist, and every test in the file dies with FileNotFoundError before
a single assertion runs.

Creating the directory is enough, and is preferable to chdir'ing: it keeps
pytest's own paths, coverage roots and failure output pointing at the app.
"""

import os
import pathlib

_APP = pathlib.Path(__file__).resolve().parents[2]  # apps/narjes_custom
_BENCH_SIBLING_LOGS = _APP.parent / "logs"  # apps/logs — what frappe reaches for


def pytest_configure(config):
    for d in (_BENCH_SIBLING_LOGS, _APP / "logs"):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            # A read-only checkout is fine; the logger only needs one of these
            # to succeed, and the tests do not read what it writes.
            pass
    # Frappe checks this before doing site-bound work; setting it keeps any
    # accidental site access loud rather than silently reaching for a default.
    os.environ.setdefault("FRAPPE_ENV", "test")
