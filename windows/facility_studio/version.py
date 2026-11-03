"""One product version for windows, reports, exports and diagnostics."""

import os

VERSION = "5.7.2"
REVISION = "preview.1"
if os.environ.get("FACILITY_STUDIO_SANDBOX"):
    VERSION = "5.7.2"
    REVISION = "preview.1"
REPORT_VERSION = VERSION + " · Windows " + REVISION
BUILD_VERSION = VERSION + "-" + REVISION
