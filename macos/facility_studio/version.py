"""One product version for windows, reports, exports and diagnostics."""

import os

VERSION = "5.6.0"
REVISION = "mac.8"
if os.environ.get("FACILITY_STUDIO_SANDBOX"):
    VERSION = "5.6.1"
    REVISION = "sandbox.1"
REPORT_VERSION = VERSION + " · macOS " + REVISION
BUILD_VERSION = VERSION + "-" + REVISION
