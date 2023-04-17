"""Module that is meant to hold the things that won't change
"""
import os
import platform
import sys

BUILD_TYPES = (
    "auto-build", "build", "clean", "debug", "program", "remote", "test", "traceback", "upload")
CURRENT_OS = platform.system()
EDITORS = {
    "Darwin": ("Sublime", "Atom"),
    "Linux": ("sublime_text", "atom"),
    "Windows": ("notepad++.exe", "sublime_text.exe", "atom.exe")
}
EXPECTED_MARLIN_VERSIONS = (1, 2)
MARLIN_HOME_DIR = os.getcwd().replace("\\", "/")  # make sure we're executing from the correct directory level
if "buildroot/share/vscode" in MARLIN_HOME_DIR:
    MARLIN_HOME_DIR = MARLIN_HOME_DIR[:MARLIN_HOME_DIR.find('buildroot/share/vscode')]
    os.chdir(MARLIN_HOME_DIR)
PYTHON_VER = sys.version_info[0]  # major version - 2 or 3
