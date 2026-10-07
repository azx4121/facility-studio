"""Checks of the shipped tutorial entry, persistent credit and actual practice load."""

import copy
import tempfile
from unittest.mock import patch

from .tutorial_help import prepare_tutorial
from .workspace_store import read_workspace


def run(root, app, workbench, check, pump):
    def visible_credit():
        widget = app.author_credit
        return (widget.winfo_ismapped() and "ANDY HUANG ©" in widget.cget("text")
                and widget.winfo_y() >= 0
                and widget.winfo_y() + widget.winfo_height() <= widget.master.winfo_height())

    check("Simple tools retain visible Andy Huang credit", visible_credit)
    initial_geometry = root.geometry()
    root.geometry("780x560+0+0")
    pump()
    check("Author credit and tutorial entry fit the minimum window", lambda:
          visible_credit() and app.tutorial_button.winfo_ismapped()
          and app.tutorial_button.winfo_y() >= 0)
    root.geometry(initial_geometry)
    pump()
    with tempfile.TemporaryDirectory(prefix="facility-tutorial-check-") as directory:
        folder = prepare_tutorial(directory)
        check("Offline guide and both practice workspaces are bundled", lambda:
              (folder / "START_HERE.html").is_file()
              and read_workspace(folder / "01_Practice_AHU.json")["main"]["inputs"]["en_L_A"] == "12"
              and len(read_workspace(folder / "02_Practice_MAU_and_AHU.json")["ahus"]) == 1)
        with patch("facility_studio.tutorial_help.prepare_tutorial", return_value=folder), \
             patch("facility_studio.tutorial_help.webbrowser.open", return_value=True) as launch:
            app.tutorial_button.invoke()
            check("Simple tutorial entry opens a local file, not a website", lambda:
                  launch.call_args.args[0].startswith("file:")
                  and launch.call_args.args[0].endswith("#start"))
            workbench.tutorial_button.invoke()
            check("Workbench tutorial entry starts at the first project", lambda:
                  launch.call_args.args[0].endswith("#first-case"))
        previous = copy.deepcopy(workbench.session_snapshot())
        previous_path = workbench.path
        try:
            workbench.apply_workspace(read_workspace(folder / "01_Practice_AHU.json"))
            workbench.recalculate()
            pump()
            check("Practice workspace loads into actual workbench and calculates", lambda:
                  workbench.result is not None
                  and workbench.result["light"]["qty"] == 25
                  and abs(workbench.result["qs"] - 7.869996) < 1e-8
                  and workbench.result["quality"]["failed"] == 0)
            workbench.show_page(8)
            pump()
            check("Actual ninth Design report page is visible", lambda:
                  workbench.pages[8].winfo_ismapped() == 1)
        finally:
            workbench.apply_workspace(previous, previous_path)
            workbench.recalculate()
            workbench.show_page(0)
            pump()
