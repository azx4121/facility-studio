"""Open a bundled offline tutorial without requiring a network connection."""

from hashlib import sha256
from pathlib import Path
import webbrowser
import zipfile

from .localized_tk import messagebox
from .project_store import app_data

TUTORIAL_FILES = {
    "START_HERE.html", "READ_ME_FIRST.txt", "01_Practice_AHU.json",
    "02_Practice_MAU_and_AHU.json", "expected-results.json",
    "01_Expected_Report.txt", "01_Expected_Report.en.txt",
    "02_Expected_AHU_Report.txt", "02_Expected_AHU_Report.en.txt",
    "LICENSE", "LICENSE_GUIDE.md", "LICENSE_GUIDE.en.md", "LICENSE_LEGACY_MIT",
}
SECTIONS = {"start", "interface", "first-case", "inputs", "results", "export",
            "utilities", "ahu", "recovery", "faq"}


def prepare_tutorial(destination=None):
    """Use a content-specific folder; never overwrite an existing practice file."""
    source = Path(__file__).with_name("resources") / "beginner_tutorial.zip"
    content = source.read_bytes()
    folder = (Path(destination) if destination is not None else app_data() / "Tutorial")
    folder = folder / ("V5_5_5_r2_" + sha256(content).hexdigest()[:16])
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if {entry.filename for entry in entries} != TUTORIAL_FILES or len(entries) != len(TUTORIAL_FILES):
            raise ValueError("Bundled tutorial contains unexpected or duplicate files")
        if sum(entry.file_size for entry in entries) > 5_000_000:
            raise ValueError("Bundled tutorial is unexpectedly large")
        for entry in entries:
            target = folder / entry.filename
            if target.is_symlink():
                raise ValueError("Tutorial destination must not contain symbolic links")
            if not target.exists():
                # Exclusive creation preserves a user's existing practice project.
                with target.open("xb") as output:
                    output.write(archive.read(entry))
    return folder


def open_tutorial(parent=None, section="start"):
    """Open local HTML; show its path when no browser association is available."""
    try:
        folder = prepare_tutorial()
        anchor = section if section in SECTIONS else "start"
        page = folder / "START_HERE.html"
        if not webbrowser.open(page.resolve().as_uri() + "#" + anchor):
            messagebox.showinfo("新手教學", "教學檔案位置：\n" + str(page), parent=parent)
        return folder
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
        messagebox.showerror("新手教學", "無法開啟離線教學：\n" + str(error), parent=parent)
        return None
