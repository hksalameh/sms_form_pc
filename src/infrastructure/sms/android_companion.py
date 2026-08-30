import os
import shutil
import subprocess
import sys
import time
from typing import Optional


COMPANION_PACKAGE = "com.smshks.companion"
COMPANION_ACTIVITY = f"{COMPANION_PACKAGE}/.MainActivity"
HOST_PORT = 8000
DEVICE_PORT = 8000


def _bundle_root() -> str:
    return getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))


def _find_adb() -> Optional[str]:
    bundled = os.path.join(_bundle_root(), "adb", "adb.exe")
    if os.path.isfile(bundled):
        return bundled
    return shutil.which("adb")


def _find_companion_apk() -> Optional[str]:
    candidates = [
        os.path.join(_bundle_root(), "android", "SmsHks-Phone.apk"),
        os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
            "android_app",
            "app",
            "build",
            "outputs",
            "apk",
            "debug",
            "app-debug.apk",
        ),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _run_adb(adb: str, args: list[str], timeout: float = 6.0) -> subprocess.CompletedProcess:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        [adb, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=creation_flags,
        check=False,
    )


def _connected_device(adb: str) -> tuple[Optional[str], str]:
    try:
        result = _run_adb(adb, ["devices"], timeout=3.0)
    except (OSError, subprocess.TimeoutExpired):
        return None, "تعذر تشغيل ADB"

    unauthorized = False
    offline = False
    for raw_line in (result.stdout or "").splitlines()[1:]:
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        if state == "device":
            return serial, ""
        if state == "unauthorized":
            unauthorized = True
        elif state == "offline":
            offline = True

    if unauthorized:
        return None, "الهاتف موجود لكن لم يوافق على USB debugging. افتح الهاتف واضغط سماح لهذا الكمبيوتر"
    if offline:
        return None, "الهاتف ظاهر في ADB لكنه Offline. افصل USB وأعد توصيله"
    return None, "لم يظهر هاتف مصرح به في ADB. فعّل USB debugging من خيارات المطور"


def _is_installed(adb: str, serial: str) -> bool:
    try:
        result = _run_adb(
            adb,
            ["-s", serial, "shell", "pm", "path", COMPANION_PACKAGE],
            timeout=4.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and "package:" in (result.stdout or "")


def _grant_permissions(adb: str, serial: str) -> None:
    permissions = [
        "android.permission.SEND_SMS",
        "android.permission.POST_NOTIFICATIONS",
    ]
    for permission in permissions:
        try:
            _run_adb(
                adb,
                ["-s", serial, "shell", "pm", "grant", COMPANION_PACKAGE, permission],
                timeout=3.0,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass


def _launch_companion(adb: str, serial: str) -> None:
    try:
        _run_adb(
            adb,
            ["-s", serial, "shell", "am", "start", "-n", COMPANION_ACTIVITY],
            timeout=4.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _setup_port_forward(adb: str, serial: str) -> tuple[bool, str]:
    """Map localhost:8000 on Windows directly to port 8000 on the USB phone."""
    try:
        result = _run_adb(
            adb,
            ["-s", serial, "forward", f"tcp:{HOST_PORT}", f"tcp:{DEVICE_PORT}"],
            timeout=4.0,
        )
    except subprocess.TimeoutExpired:
        return False, "انتهت مهلة إنشاء قناة USB المباشرة"
    except OSError as exc:
        return False, f"تعذر إنشاء قناة USB: {exc}"

    if result.returncode == 0:
        return True, ""

    output = f"{result.stdout}\n{result.stderr}".strip()
    if not output:
        output = "ADB forward failed"
    return False, f"تعذر ربط منفذ USB: {output[-220:]}"


def ensure_companion_app(auto_install: bool = True) -> tuple[bool, str]:
    """Ensure SmsHks Phone is installed, launched and reachable through USB ADB."""
    adb = _find_adb()
    if not adb:
        return False, "ADB غير موجود داخل نسخة SmsHks"

    serial, error = _connected_device(adb)
    if not serial:
        return False, error

    installed = _is_installed(adb, serial)
    if not installed:
        if not auto_install:
            return False, "الهاتف متصل لكن تطبيق SmsHks Phone غير مثبت"

        apk = _find_companion_apk()
        if not apk:
            return False, "ملف SmsHks Phone APK غير موجود داخل البرنامج"

        try:
            result = _run_adb(
                adb,
                ["-s", serial, "install", "-r", apk],
                timeout=45.0,
            )
        except subprocess.TimeoutExpired:
            return False, "استغرق تثبيت تطبيق الهاتف وقتاً طويلاً"
        except OSError as exc:
            return False, f"تعذر تثبيت تطبيق الهاتف: {exc}"

        output = f"{result.stdout}\n{result.stderr}"
        if result.returncode != 0 or "Success" not in output:
            return False, f"فشل تثبيت تطبيق الهاتف: {output.strip()[-220:]}"
        installed = True

    if installed:
        _grant_permissions(adb, serial)
        forward_ok, forward_error = _setup_port_forward(adb, serial)
        if not forward_ok:
            return False, forward_error

        _launch_companion(adb, serial)
        time.sleep(0.9)
        return True, "تطبيق SmsHks Phone جاهز وقناة USB المباشرة تعمل"

    return False, "تعذر تجهيز تطبيق SmsHks Phone"
