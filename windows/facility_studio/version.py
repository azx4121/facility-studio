"""One product version for windows, reports, exports and diagnostics."""

import os

VERSION = "5.6.0"
REVISION = "win.10"
if os.environ.get("FACILITY_STUDIO_SANDBOX"):
    VERSION = "5.6.1"
    REVISION = "win-sandbox.2"
REPORT_VERSION = VERSION + " · Windows " + REVISION
BUILD_VERSION = VERSION + "-" + REVISION
