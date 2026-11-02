"""One product version for windows, reports, exports and diagnostics."""

import os

VERSION = "5.7.0"
REVISION = "fusion.1"
if os.environ.get("FACILITY_STUDIO_SANDBOX"):
    VERSION = "5.7.0"
    REVISION = "fusion.1"
REPORT_VERSION = VERSION + " · macOS " + REVISION
BUILD_VERSION = VERSION + "-" + REVISION
