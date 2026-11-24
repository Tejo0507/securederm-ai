"""Cap the size of a request body as it is read.

Checking the Content-Length header alone is not enough: a chunked request sends
no such header, so it passed that check and could stream any amount of data
into memory or onto disk. This counts the bytes that actually arrive.
"""

from typing import Callable

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

TOO_LARGE_DETAIL = "Request body too large."


class StreamingBodyLimit:
    """ASGI middleware that answers 413 once a body exceeds `max_bytes()`.

    The limit is a callable so it is read per request. Add this middleware
    before any other, so that it sits closest to the routes and the 413 passes
    through the same header and CORS handling as every other response.
    """

    def __init__(self, app: ASGIApp, max_bytes: Callable[[], int]) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = self.max_bytes()
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # An HTTPException passes through FastAPI's body parsing
                    # unchanged and becomes an ordinary error response.
                    raise HTTPException(status_code=413, detail=TOO_LARGE_DETAIL)
            return message

        await self.app(scope, limited_receive, send)
