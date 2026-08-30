import asyncio
import time


class Throttler:
    def __init__(self, delay_ms: int = 1000):
        self.delay = delay_ms / 1000.0
        self._last_send_time: float = 0

    async def wait(self):
        if self.delay <= 0:
            return
        elapsed = time.time() - self._last_send_time
        if elapsed < self.delay:
            await asyncio.sleep(self.delay - elapsed)

    def record_send(self):
        self._last_send_time = time.time()

    def set_delay(self, delay_ms: int):
        self.delay = delay_ms / 1000.0


class AdaptiveThrottler(Throttler):
    def __init__(self, delay_ms: int = 1000):
        super().__init__(delay_ms)
        self._consecutive_failures = 0
        self._base_delay = delay_ms

    def record_failure(self):
        self._consecutive_failures += 1
        if self._consecutive_failures >= 3:
            new_delay = min(self._base_delay * (2 ** (self._consecutive_failures - 2)), 30000)
            self.set_delay(new_delay)

    def record_success(self):
        if self._consecutive_failures > 0:
            self._consecutive_failures -= 1
            if self._consecutive_failures == 0:
                self.set_delay(self._base_delay)
