import unittest
from unittest.mock import AsyncMock, patch

import phone_server.main as phone_server


class FakeSerial:
    def __init__(self):
        self.is_open = True
        self.in_waiting = 0
        self.writes = []

    def write(self, data: bytes):
        self.writes.append(data)


class PhoneServerSerialTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_sms_body_appends_real_ctrl_z_byte(self):
        fake_serial = FakeSerial()
        original_serial = phone_server.ser
        phone_server.ser = fake_serial
        expected_response = "+CMGS: 1\r\nOK\r\n"

        try:
            with patch.object(
                phone_server,
                "_read_serial_response",
                new=AsyncMock(return_value=expected_response),
            ) as read_response:
                response = await phone_server.send_sms_body("مرحبا")

            self.assertEqual(
                fake_serial.writes,
                ["مرحبا".encode("utf-8") + bytes([26])],
            )
            self.assertEqual(response, expected_response)
            read_response.assert_awaited_once_with(10.0)
        finally:
            phone_server.ser = original_serial


if __name__ == "__main__":
    unittest.main()
