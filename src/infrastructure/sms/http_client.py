import asyncio
from typing import Optional

import httpx

from src.domain.entities import PhoneConfig
from src.infrastructure.sms.android_companion import ensure_companion_app
from src.infrastructure.sms.device_detector import (
    detect_android_usb,
    detect_usb_tethering_gateway,
)


class PhoneHttpClient:
    HEALTH_TIMEOUT_SECONDS = 1.5
    USB_HOST = "127.0.0.1"

    def __init__(self, config: PhoneConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(self.config.timeout_ms / 1000.0, connect=2.0),
            )
        return self._client

    def _usb_base_url(self) -> str:
        return f"http://{self.USB_HOST}:{self.config.port}"

    async def _probe_health(self, base_url: Optional[str] = None) -> tuple[bool, str]:
        timeout = httpx.Timeout(self.HEALTH_TIMEOUT_SECONDS, connect=1.0)
        try:
            if base_url is None:
                client = await self._get_client()
                resp = await client.get("/health", timeout=timeout)
            else:
                async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
                    resp = await client.get("/health")

            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code}"
            data = resp.json()
            status = str(data.get("status", "ok"))
            return status.lower() == "connected", status
        except httpx.ConnectTimeout:
            return False, "انتهت مهلة الوصول لخدمة الإرسال"
        except httpx.ConnectError:
            return False, "خدمة الإرسال غير متصلة"
        except httpx.TimeoutException:
            return False, "انتهت مهلة خدمة الإرسال"
        except Exception as exc:
            return False, str(exc)

    async def _switch_to_host(self, host: str) -> None:
        if not host or host == self.config.ip_address:
            return
        await self.close()
        self.config.ip_address = host

    async def health_check(self) -> tuple[bool, str]:
        """Prepare the Android companion and prefer the direct USB ADB tunnel."""
        usb_task = asyncio.create_task(
            asyncio.to_thread(detect_android_usb, self.HEALTH_TIMEOUT_SECONDS)
        )
        companion_task = asyncio.create_task(
            asyncio.to_thread(ensure_companion_app, True)
        )

        try:
            companion_ready, companion_status = await companion_task
        except Exception as exc:
            companion_ready, companion_status = False, str(exc)

        if companion_ready:
            usb_url = self._usb_base_url()
            usb_ok, usb_status = await self._probe_health(usb_url)
            if not usb_ok:
                # The activity may need a brief moment to promote the service.
                await asyncio.sleep(0.6)
                usb_ok, usb_status = await self._probe_health(usb_url)

            if usb_ok:
                await self._switch_to_host(self.USB_HOST)
                return True, "connected"

            if str(usb_status).lower() == "permission_required":
                return True, (
                    "تم الاتصال بالهاتف عبر USB، لكن تطبيق SmsHks Phone يحتاج صلاحية إرسال SMS"
                )

            return True, (
                "تم تجهيز الهاتف وقناة USB المباشرة، لكن خدمة SmsHks Phone لم تستجب بعد: "
                f"{usb_status}. افتح التطبيق على الهاتف واضغط تشغيل خدمة SmsHks"
            )

        try:
            usb_found, device_name = await usb_task
        except Exception:
            usb_found, device_name = False, ""

        # Compatibility fallback: keep the old network/tethering path available.
        configured_ok, configured_status = await self._probe_health()
        if configured_ok:
            return True, "connected"

        try:
            gateway = await asyncio.to_thread(detect_usb_tethering_gateway, 1.5)
        except Exception:
            gateway = ""

        if gateway:
            gateway_url = f"http://{gateway}:{self.config.port}"
            gateway_ok, gateway_status = await self._probe_health(gateway_url)
            if gateway_ok:
                await self._switch_to_host(gateway)
                return True, "connected"
            configured_status = gateway_status or configured_status

        if usb_found:
            label = f" ({device_name})" if device_name else ""
            return True, f"تم العثور على هاتف Android{label}، لكن {companion_status}"

        return False, companion_status or configured_status or "لم يتم العثور على هاتف Android جاهز"

    async def _post_sms(self, base_url: Optional[str], phone: str, text: str):
        headers = {"X-API-Token": self.config.api_token} if self.config.api_token else {}
        request_timeout = httpx.Timeout(
            self.config.timeout_ms / 1000.0,
            connect=2.0,
        )
        if base_url is None:
            client = await self._get_client()
            return await client.post(
                "/send",
                json={"phone": phone, "text": text},
                headers=headers,
                timeout=request_timeout,
            )

        async with httpx.AsyncClient(base_url=base_url, timeout=request_timeout) as client:
            return await client.post(
                "/send",
                json={"phone": phone, "text": text},
                headers=headers,
            )

    @staticmethod
    def _parse_send_response(resp: httpx.Response) -> tuple[bool, str]:
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                return True, data.get("message_id", "")
            return False, data.get("error", "فشل الإرسال من الهاتف")
        try:
            data = resp.json()
            detail = data.get("error") or data.get("detail")
            if detail:
                return False, str(detail)
        except Exception:
            pass
        return False, f"HTTP {resp.status_code}: {resp.text}"

    async def send_sms(self, phone: str, text: str) -> tuple[bool, str]:
        try:
            resp = await self._post_sms(None, phone, text)
            return self._parse_send_response(resp)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            # Repair/install the Android companion and recreate the USB tunnel.
            try:
                companion_ready, companion_status = await asyncio.to_thread(
                    ensure_companion_app, True
                )
            except Exception as exc:
                companion_ready, companion_status = False, str(exc)

            if companion_ready:
                try:
                    resp = await self._post_sms(self._usb_base_url(), phone, text)
                    result = self._parse_send_response(resp)
                    await self._switch_to_host(self.USB_HOST)
                    return result
                except httpx.TimeoutException:
                    return False, "انتهت مهلة الاتصال بتطبيق SmsHks Phone عبر USB"
                except httpx.ConnectError:
                    pass

            # Compatibility fallback for users who still prefer USB tethering.
            try:
                gateway = await asyncio.to_thread(detect_usb_tethering_gateway, 1.5)
            except Exception:
                gateway = ""

            if gateway:
                try:
                    resp = await self._post_sms(
                        f"http://{gateway}:{self.config.port}",
                        phone,
                        text,
                    )
                    result = self._parse_send_response(resp)
                    if result[0]:
                        await self._switch_to_host(gateway)
                    return result
                except httpx.TimeoutException:
                    return False, "انتهت مهلة الاتصال بخدمة الإرسال على الهاتف"
                except httpx.ConnectError:
                    pass

            return False, companion_status or "تعذر الاتصال بخدمة SmsHks Phone على الهاتف"
        except httpx.TimeoutException:
            return False, "انتهت مهلة الاتصال بالهاتف"
        except Exception as e:
            return False, str(e)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
