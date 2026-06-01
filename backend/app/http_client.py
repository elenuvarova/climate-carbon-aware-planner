import httpx

_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP client not initialised — call init() first")
    return _client


async def init() -> None:
    global _client
    _client = httpx.AsyncClient(timeout=20.0, follow_redirects=True)


async def close() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None
