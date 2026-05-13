from collections.abc import Mapping

import httpx
from fastapi import Request, Response


_client: httpx.AsyncClient | None = None
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


async def get_proxy_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


async def close_proxy_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def clean_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }


async def forward_request(
    request: Request,
    target_url: str,
    user_id: str | None = None,
) -> Response:
    client = await get_proxy_client()
    headers = clean_headers(request.headers)
    if user_id:
        headers["X-User-Id"] = user_id

    upstream_response = await client.request(
        method=request.method,
        url=target_url,
        params=request.query_params,
        content=await request.body(),
        headers=headers,
    )
    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        media_type=upstream_response.headers.get("content-type"),
    )
