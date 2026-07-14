"""API helper — wraps Playwright's APIRequestContext with logging and
response capture so step definitions stay one-liners.
"""
import json
import os
import time

from .logger import logger


class ApiHelper:
    def __init__(self, playwright, base_url: str | None = None):
        self._playwright = playwright
        self.base_url = base_url or os.environ.get("API_BASE_URL")
        self.context = None
        self.last_response = None
        self.last_body = None

    def init(self, extra_headers: dict | None = None):
        self.context = self._playwright.request.new_context(
            base_url=self.base_url,
            extra_http_headers={"Content-Type": "application/json", **(extra_headers or {})},
        )
        return self

    def send(self, method: str, endpoint: str, data=None, params=None, headers=None):
        if self.context is None:
            self.init()
        started = time.monotonic()
        response = self.context.fetch(
            endpoint, method=method.upper(), data=data, params=params, headers=headers
        )
        elapsed = int((time.monotonic() - started) * 1000)
        self.last_response = response
        try:
            self.last_body = response.json()
        except Exception:
            self.last_body = response.text()
        logger.info(f"API {method.upper()} {endpoint} -> {response.status} ({elapsed}ms)")
        logger.debug(f"API response body: {json.dumps(self.last_body, default=str)[:2000]}")
        return response

    def get(self, endpoint, **kwargs):
        return self.send("GET", endpoint, **kwargs)

    def post(self, endpoint, data=None, **kwargs):
        return self.send("POST", endpoint, data=data, **kwargs)

    def put(self, endpoint, data=None, **kwargs):
        return self.send("PUT", endpoint, data=data, **kwargs)

    def patch(self, endpoint, data=None, **kwargs):
        return self.send("PATCH", endpoint, data=data, **kwargs)

    def delete(self, endpoint, **kwargs):
        return self.send("DELETE", endpoint, **kwargs)

    def status(self):
        return self.last_response.status if self.last_response else None

    def body(self):
        return self.last_body

    def body_path(self, dotted_path: str):
        """Resolve a dotted path ("data.0.email") against the last response body."""
        value = self.last_body
        for key in dotted_path.split("."):
            if value is None:
                return None
            if isinstance(value, list):
                try:
                    value = value[int(key)]
                except (ValueError, IndexError):
                    return None
            elif isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def dispose(self):
        if self.context is not None:
            self.context.dispose()
            self.context = None
