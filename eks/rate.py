import asyncio
import logging
from typing import Optional

# Define the RateLimiter class using an asyncio.Semaphore
class RateLimiter:
    """
    An asynchronous rate limiter using an asyncio.Semaphore.
    It can be used as an async context manager to limit the number
    of concurrent executions of a block of code.
    """

    def __init__(self, max_concurrent: int, name: Optional[str] = None):
        """
        Initializes the RateLimiter.

        Args:
            max_concurrent: The maximum number of concurrent tasks allowed.
            name: An optional name for logging/identification.
        """
        if max_concurrent <= 0:
            raise ValueError("max_concurrent must be a positive integer.")
        self.max_concurrent = max_concurrent
        self.name = name if name else "UnnamedRateLimiter"
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.logger = logging.getLogger(self.name) # Use the name for the logger

    async def __aenter__(self):
        """
        Acquire the semaphore, blocking until a slot is available.
        This method is called when entering the 'async with' block.
        """
        self.logger.debug(f"Waiting to acquire lock on '{self.name}'. Available: {self._semaphore._value}")
        # The 'acquire' call is where the execution may pause if the limit is reached.
        await self._semaphore.acquire()
        self.logger.debug(f"Lock acquired on '{self.name}'. Remaining: {self._semaphore._value}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Release the semaphore, making a slot available for a waiting task.
        This method is called when exiting the 'async with' block (even if an exception occurred).
        """
        self._semaphore.release()
        self.logger.debug(f"Lock released on '{self.name}'. Available: {self._semaphore._value}")
        # Return True if you want to suppress an exception, otherwise let it propagate.
        # We don't suppress exceptions here, so no explicit return is needed.

    @property
    def current_value(self) -> int:
        """
        Returns the current value of the semaphore (number of available slots).
        """
        return self._semaphore._value

    def __repr__(self):
        return f"<RateLimiter name='{self.name}' max_concurrent={self.max_concurrent} current={self.current_value}>"

