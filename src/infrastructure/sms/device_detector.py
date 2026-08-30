import os
import subprocess
import sys


_ANDROID_NAME_PATTERN = (
    "Android|ADB|MTP|Samsung|Galaxy|Pixel|Xiaomi|Redmi|Huawei|Honor|"
    "OnePlus|OPPO|vivo|Motorola|realme|Nothing Phone"
)
_TETHERING_ADAPTER_PATTERN = (
    "RNDIS|Remote NDIS|Android|Samsung|Galaxy|Xiaomi|Huawei|Honor|"
    "OnePlus|OPPO|vivo|Motorola|realme|USB Mobile|USB Ethernet"
)


def _powershell_path() -> str:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return os.path.join(
        system_root,
        "System32",
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe",
    )


def _run_powershell(script: str, timeout_seconds: float) -> list[str]:
    if sys.platform != "win32":
        return []

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [
                _powershell_path(),
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=max(0.5, timeout_seconds),
            creationflags=creation_flags,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


def detect_android_usb(timeout_seconds: float = 1.5) -> tuple[bool, str]:
    """Quickly detect a physically connected Android-like device on Windows."""
    script = (
        "$ErrorActionPreference='SilentlyContinue'; "
        "Get-PnpDevice -PresentOnly | "
        f"Where-Object {{ $_.Status -eq 'OK' -and $_.FriendlyName -match '{_ANDROID_NAME_PATTERN}' }} | "
        "Select-Object -First 1 -ExpandProperty FriendlyName"
    )
    lines = _run_powershell(script, timeout_seconds)
    if lines:
        return True, lines[0]
    return False, ""


def detect_usb_tethering_gateway(timeout_seconds: float = 1.5) -> str:
    """Return the phone/gateway IPv4 address for an Android USB tethering adapter."""
    script = (
        "$ErrorActionPreference='SilentlyContinue'; "
        "$routes = Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' | "
        "Sort-Object RouteMetric; "
        "foreach ($route in $routes) { "
        "$adapter = Get-NetAdapter -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue; "
        "$label = (($adapter.Name) + ' ' + ($adapter.InterfaceDescription)); "
        f"if ($adapter -and $label -match '{_TETHERING_ADAPTER_PATTERN}' -and $route.NextHop -ne '0.0.0.0') {{ "
        "Write-Output $route.NextHop; break } }"
    )
    lines = _run_powershell(script, timeout_seconds)
    return lines[0] if lines else ""
