"""One product version for windows, reports, exports and diagnostics."""

import os

VERSION = "5.7.0"
REVISION = "fusion.2"
if os.environ.get("FACILITY_STUDIO_SANDBOX"):
    VERSION = "5.7.0"
    REVISION = "fusion.2"
REPORT_VERSION = VERSION + " · Windows " + REVISION
BUILD_VERSION = VERSION + "-" + REVISION
