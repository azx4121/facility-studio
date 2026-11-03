"""The 5.7.3 candidate must not reuse the bundle identity of the delivered 5.7.1 App."""
from pathlib import Path

BUILD = (Path(__file__).resolve().parent / "build.py").read_text(encoding="utf-8")


def test_mac_bundle_identifier_is_distinct_from_previous_delivery():
    assert '"--osx-bundle-identifier", "com.facilitystudio.preview573"' in BUILD
    assert "preview572" not in BUILD and "preview571" not in BUILD and "engineeringfusion" not in BUILD
