"""
Phone SMS Server - يعمل على الهاتف المتصل بالكمبيوتر
يستقبل طلبات HTTP من برنامج SMSCaster Desktop ويرسل SMS عبر منفذ Serial (AT Commands)
"""

import asyncio
import logging
import os
import re
from typing import Optional
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phone_server")

app = FastAPI(title="Phone SMS Server", version="1.0.0")

SERIAL_PORT: Optional[str] = None
BAUD_RATE: int = 115200
SERVER_HOST: str = os.environ.get("PHONE_SERVER_HOST", "127.0.0.1")
SERVER_PORT: int = int(os.environ.get("PHONE_SERVER_PORT", "8000"))
API_TOKEN: str = os.environ.get("PHONE_SERVER_API_TOKEN", "")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
REQUIRE_API_TOKEN = bool(API_TOKEN) or SERVER_HOST not in LOOPBACK_HOSTS
ser: Optional = None
serial_lock = asyncio.Lock()

PHONE_RE = re.compile(r"^\+?\d{3,20}$")
MAX_SMS_TEXT_LENGTH = 1600


class SendRequest(BaseModel):
    phone: str
    text: str


class SendResponse(BaseModel):
    success: bool
    message_id: str = ""
    error: str = ""



def verify_api_token(token: Optional[str]) -> None:
    if not REQUIRE_API_TOKEN:
        return
    if not API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="PHONE_SERVER_API_TOKEN is required when the server is not bound to localhost",
        )
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API token")


def sanitize_phone(phone: str) -> str:
    cleaned = re.sub(r"[\s().-]", "", phone.strip())
    if not PHONE_RE.fullmatch(cleaned):
        raise HTTPException(status_code=400, detail="Invalid phone number")
    return cleaned


def sanitize_text(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Message text is required")
    if len(cleaned) > MAX_SMS_TEXT_LENGTH:
        raise HTTPException(status_code=400, detail="Message text is too long")

    blocked_controls = {"\x00", "\x1a", "\x1b", "\r"}
    if any(ch in cleaned for ch in blocked_controls):
        raise HTTPException(status_code=400, detail="Message text contains unsafe control characters")
    return cleaned

def detect_serial_port() -> Optional[str]:
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        for p in ports:
            if "USB" in p.description or "COM" in p.device:
                logger.info(f"Found port: {p.device} - {p.description}")
                return p.device
    except Exception as e:
        logger.error(f"Port detection error: {e}")
    return None


def open_serial(port: str, baud: int = 115200):
    global ser
    try:
        import serial
        ser = serial.Serial(port, baud, timeout=5)
        logger.info(f"Connected to {port} at {baud} baud")
        return True
    except Exception as e:
        logger.error(f"Failed to open {port}: {e}")
        return False


async def send_at_command(command: str, timeout: float = 3.0) -> str:
    if not ser or not ser.is_open:
        return ""
    try:
        ser.write((command + "\r").encode())
        await asyncio.sleep(0.1)
        response = b""
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
            if ser.in_waiting:
                response += ser.read(ser.in_waiting)
            else:
                await asyncio.sleep(0.05)
        return response.decode(errors="replace")
    except Exception as e:
        logger.error(f"AT command error: {e}")
        return ""


async def send_sms_serial(phone: str, text: str) -> tuple[bool, str]:
    async with serial_lock:
        try:
            resp = await send_at_command("AT")
            if "OK" not in resp:
                return False, "Device is not responding"

            resp = await send_at_command('AT+CMGF=1')
            if "OK" not in resp:
                return False, "Failed to set text mode"

            resp = await send_at_command(f'AT+CMGS="{phone}"')
            if ">" not in resp:
                return False, "Failed to start sending"

            resp = await send_at_command(text + "\\x1a", timeout=10.0)
            if "OK" in resp or "CMGS" in resp:
                return True, "Sent"
            return False, f"Send failed: {resp[:100]}"
        except Exception as e:
            return False, str(e)


@app.on_event("startup")
async def startup():
    global SERIAL_PORT
    SERIAL_PORT = detect_serial_port()
    if SERIAL_PORT:
        open_serial(SERIAL_PORT, BAUD_RATE)


@app.on_event("shutdown")
async def shutdown():
    global ser
    if ser and ser.is_open:
        ser.close()


@app.get("/health")
async def health():
    status = "connected" if ser and ser.is_open else "disconnected"
    return {
        "status": status,
        "port": SERIAL_PORT or "none",
        "baud": BAUD_RATE,
    }


@app.post("/send", response_model=SendResponse)
async def send_sms(req: SendRequest, x_api_token: Optional[str] = Header(default=None)):
    verify_api_token(x_api_token)
    if not ser or not ser.is_open:
        raise HTTPException(status_code=503, detail="Phone not connected")

    phone = sanitize_phone(req.phone)
    text = sanitize_text(req.text)
    success, msg = await send_sms_serial(phone, text)
    return SendResponse(success=success, error="" if success else msg)



if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
