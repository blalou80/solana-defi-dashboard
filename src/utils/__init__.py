import asyncio
import logging
import sys
import time
from functools import wraps
from typing import Callable, TypeVar

T = TypeVar('T')

def setup_logging(level=logging.INFO):
    """Configure logging with structured format."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    # Optionally add rotation later

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for exponential backoff retry on exceptions."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            _delay = delay
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    logging.getLogger(func.__module__).warning(
                        f"Attempt {attempt+1} failed: {e}. Retrying in {_delay}s"
                    )
                    time.sleep(_delay)
                    _delay *= backoff
            # Should never reach here
            raise RuntimeError("Retry exhausted")
        return wrapper
    return decorator

# Async version
def async_retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for async functions with exponential backoff."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            _delay = delay
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    logging.getLogger(func.__module__).warning(
                        f"Attempt {attempt+1} failed: {e}. Retrying in {_delay}s"
                    )
                    await asyncio.sleep(_delay)
                    _delay *= backoff
            raise RuntimeError("Retry exhausted")
        return wrapper
    return decorator
