"""Live image sources behind one adapter (SPEC 6-b).

Tenor / GIPHY search for transparent stickers. Both are optional: with no
API key in .env the adapter returns nothing and the wizard falls back to
internal sources only. Results are normalized to suggestion-pool items:
{"id": "tenor:<id>", "label": title, "file_url": <webp/png url>}.
"""
from __future__ import annotations

import aiohttp

from .config import config

_TIMEOUT = aiohttp.ClientTimeout(total=12)


async def tenor_search(query: str, limit: int = 6) -> list[dict]:
    if not config.tenor_api_key:
        return []
    url = "https://tenor.googleapis.com/v2/search"
    params = {
        "q": query or "sticker",
        "key": config.tenor_api_key,
        "limit": str(limit),
        "searchfilter": "sticker",
        "media_filter": "webp_transparent,tinygif_transparent",
    }
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.get(url, params=params) as r:
                if r.status != 200:
                    return []
                data = await r.json()
    except Exception:
        return []
    out: list[dict] = []
    for item in data.get("results", []):
        fmts = item.get("media_formats", {})
        media = fmts.get("webp_transparent") or fmts.get("tinygif_transparent") or {}
        if media.get("url"):
            out.append({
                "id": f"tenor:{item.get('id')}",
                "label": (item.get("content_description") or "استیکر وب")[:60],
                "file_url": media["url"],
                "source": "tenor",
            })
    return out


async def giphy_search(query: str, limit: int = 6) -> list[dict]:
    if not config.giphy_api_key:
        return []
    url = "https://api.giphy.com/v1/stickers/search"
    params = {"q": query or "sticker", "api_key": config.giphy_api_key,
              "limit": str(limit)}
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.get(url, params=params) as r:
                if r.status != 200:
                    return []
                data = await r.json()
    except Exception:
        return []
    out: list[dict] = []
    for item in data.get("data", []):
        images = item.get("images", {})
        media = images.get("fixed_width") or images.get("original") or {}
        link = media.get("webp") or media.get("url")
        if link:
            out.append({
                "id": f"giphy:{item.get('id')}",
                "label": (item.get("title") or "استیکر وب")[:60],
                "file_url": link,
                "source": "giphy",
            })
    return out


async def live_search(query: str, limit: int = 6) -> list[dict]:
    """Tenor first, GIPHY as fill-in. Empty when no keys are configured."""
    results = await tenor_search(query, limit)
    if len(results) < limit:
        results += await giphy_search(query, limit - len(results))
    return results[:limit]
