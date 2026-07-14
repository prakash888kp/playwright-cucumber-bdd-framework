"""Small shared utilities."""
import random
import string
import time
from datetime import date, datetime


def random_string(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def random_email(domain: str = "example.com") -> str:
    return f"qa_{random_string(10)}@{domain}"


def random_number(minimum: int = 0, maximum: int = 10_000) -> int:
    return random.randint(minimum, maximum)


def today_iso() -> str:
    return date.today().isoformat()


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def wait_until(predicate, timeout: float = 10.0, interval: float = 0.25, message: str = "condition"):
    """Poll `predicate` until truthy or timeout (seconds)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    raise TimeoutError(f"Timed out after {timeout}s waiting for {message}")
