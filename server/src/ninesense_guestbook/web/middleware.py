from collections.abc import Awaitable, Callable

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class PayloadTooLarge(Exception):
    pass


class ApiProtectionMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int = 32 * 1024):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message.setdefault("headers", []))
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Cache-Control"] = "no-store"
            await send(message)

        content_length = self._content_length(scope)
        if content_length is not None and content_length > self.max_body_bytes:
            await self._reject(scope, receive, send_with_headers)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise PayloadTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send_with_headers)
        except PayloadTooLarge:
            await self._reject(scope, receive, send_with_headers)

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return None
        return None

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Callable[[Message], Awaitable[None]],
    ) -> None:
        response = JSONResponse(
            {"detail": "请求内容过大。"},
            status_code=413,
        )
        await response(scope, receive, send)

