"""Pinned, offline expected inputs for the historical V5.5.4 installer.

The fixture comes from an immutable upstream source commit, not from the
executable under test. Current installer staging is verified separately.
"""

from io import BytesIO
import hashlib
from pathlib import Path, PurePosixPath
import zipfile

SOURCE_COMMIT = "6ada894438805a00c8c795f63451916b1d759a84"
FIXTURE_SHA256 = "567f0bb3fa3debf61a518f5597324c5833a62df8deeecb20be64f7fefff6af42"
BINARY_SHA256 = "799b3fb496881547466253154beb66d3a30f10a23838b1533a4813a69da2acc4"
FIXTURE = Path(__file__).with_name("fixtures") / "v554-installer-members.zip"
MEMBER_COUNT = 62


def historical_installer_members(path=FIXTURE):
    """Fail closed on a changed fixture, duplicate names or unsafe paths."""
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != FIXTURE_SHA256:
        raise AssertionError("Historical installer fixture SHA256 mismatch.")
    with zipfile.ZipFile(BytesIO(data)) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(infos) != MEMBER_COUNT or len(set(names)) != MEMBER_COUNT:
            raise AssertionError("Historical installer fixture member count mismatch.")
        for info in infos:
            name = PurePosixPath(info.filename)
            if (info.is_dir() or name.is_absolute() or ".." in name.parts
                    or "\\" in info.filename):
                raise AssertionError("Unsafe historical installer fixture path.")
        return {info.filename: archive.read(info) for info in infos}


def historical_installer_binary(path):
    """The regression targets this exact retained binary; never silently retarget."""
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != BINARY_SHA256:
        raise AssertionError("Historical V5.5.4 installer binary SHA256 mismatch.")
    return data
