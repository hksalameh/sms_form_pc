"""PyInstaller runtime hook for the bundled Android platform tools.

Keeps ADB beside the portable executable usable on a clean Windows PC and
starts its background server before the UI performs the first phone check.
"""

import os
import subprocess
import sys


def _initialize_bundled_adb() -> None:
    root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    adb_dir = os.path.join(root, "adb")
    adb_exe = os.path.join(adb_dir, "adb.exe")
    if not os.path.isfile(adb_exe):
        return

    # Make the official ADB DLLs discoverable when adb.exe is spawned.
    os.environ["PATH"] = adb_dir + os.pathsep + os.environ.get("PATH", "")
    try:
        add_dll_directory = getattr(os, "add_dll_directory", None)
        if add_dll_directory is not None:
            add_dll_directory(adb_dir)
    except OSError:
        pass

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.run(
            [adb_exe, "start-server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=12.0,
            creationflags=creation_flags,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        # The normal connection check will show the user a clear status later.
        pass


_initialize_bundled_adb()
