import os
import subprocess
import sys


_ANDROID_NAME_PATTERN = (
    "Android|ADB|MTP|Samsung|Galaxy|Pixel|Xiaomi|Redmi|Huawei|Honor|"
    "OnePlus|OPPO|vivo|Motorola|realme|Nothing Phone"
)


def detect_android_usb(timeout_seconds: float = 1.5) -> tuple[bool, str]:
    """Quickly detect a physically connected Android-like device on Windows.

    This only answers whether Windows can see the phone over USB. It does not
    guarantee that the SMS HTTP service is running or ready.
    """
    if sys.platform != "win32":
        return False, ""

    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    powershell = os.path.join(
        system_root,
        "System32",
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe",
    )

    script = (
        "$ErrorActionPreference='SilentlyContinue'; "
        "Get-PnpDevice -PresentOnly | "
        f"Where-Object {{ $_.Status -eq 'OK' -and $_.FriendlyName -match '{_ANDROID_NAME_PATTERN}' }} | "
        "Select-Object -First 1 -ExpandProperty FriendlyName"
    )

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=max(0.5, timeout_seconds),
            creationflags=creation_flags,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, ""

    device_name = (result.stdout or "").strip().splitlines()
    if device_name:
        return True, device_name[0].strip()
    return False, ""
