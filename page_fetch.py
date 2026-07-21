"""Fetch a web page and reduce it to glasses-friendly text + images.

The G2 renders 4-bit greyscale and image containers max out at 288x144, so
images are greyscaled, autocontrasted, and thumbnailed before being shipped
as base64 PNG (the Even host converts PNG to gray4 on device).

All functions are synchronous — the adapter runs them in an executor.
"""
from __future__ import annotations

import base64
import io
import ipaddress
import logging
import os
import re
import socket
from urllib.parse import urljoin, urlparse

log = logging.getLogger("hermes-evenhub-bridge")

MAX_TEXT = 3000
MAX_IMAGES = 3
MAX_LINKS = 19  # glasses list widget: 20 rows, row 0 is "back"
IMG_MAX_W, IMG_MAX_H = 288, 144
IMG_MIN_SOURCE = 64   # skip icons/trackers smaller than this
IMG_MIN_CONTAINER = 20  # Even image containers reject sides < 20px

_STRIP_TAGS = ["script", "style", "noscript", "template", "svg",
               "nav", "footer", "header", "aside", "form", "iframe"]

_MAX_REDIRECTS = 5
_REDIRECT_CODES = {301, 302, 303, 307, 308}


def _ensure_public_host(url: str) -> None:
    """SSRF guard: reject hosts that resolve to non-public addresses.

    Page URLs originate in LLM output; without this the bridge would happily
    fetch router admin pages, localhost services, Tailscale peers, or cloud
    metadata endpoints from the PC's network position. Deliberate LAN browsing
    can be re-enabled with EVENHUB_PAGE_FETCH_ALLOW_PRIVATE=1.
    """
    if os.environ.get("EVENHUB_PAGE_FETCH_ALLOW_PRIVATE", "").strip() == "1":
        return
    host = urlparse(url).hostname or ""
    if not host:
        raise ValueError("URL has no host")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as e:
        raise ValueError(f"cannot resolve host {host}") from e
    for info in infos:
        addr = str(info[4][0]).split("%", 1)[0]  # strip IPv6 zone id
        if not ipaddress.ip_address(addr).is_global:
            raise ValueError(f"blocked non-public address for host {host}")


def _validated_get(client, url: str):
    """GET with the SSRF guard re-applied on every redirect hop."""
    for _ in range(_MAX_REDIRECTS + 1):
        _ensure_public_host(url)
        r = client.get(url)
        location = r.headers.get("location")
        if r.status_code in _REDIRECT_CODES and location:
            url = urljoin(url, location)
            continue
        r.raise_for_status()
        return r
    raise ValueError("too many redirects")


def fetch_page(url: str) -> dict:
    """Return {url, title, text, images:[{data, width, height}]}. Raises on
    network errors; the adapter converts those into page.error frames."""
    scheme = urlparse(url).scheme
    if scheme not in ("http", "https"):
        raise ValueError(f"unsupported URL scheme: {scheme or '(none)'}")

    import httpx
    headers = {"User-Agent": "Mozilla/5.0 (compatible; hermes-evenhub-bridge)"}
    # follow_redirects=False: _validated_get walks redirects manually so the
    # SSRF guard applies to every hop, not just the first URL.
    with httpx.Client(timeout=20, follow_redirects=False, headers=headers) as client:
        r = _validated_get(client, url)
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype:
            return {"url": url, "title": url, "text": r.text[:MAX_TEXT],
                    "images": [], "links": []}

        title, text, img_urls, links = _extract(r.text, str(r.url))
        images = []
        for img_url in img_urls:
            if len(images) >= MAX_IMAGES:
                break
            img = _fetch_image(client, img_url)
            if img:
                images.append(img)
        return {"url": url, "title": title or url, "text": text[:MAX_TEXT],
                "images": images, "links": links}


def _extract(html: str, base_url: str) -> tuple[str, str, list[str], list[dict]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup

    img_urls: list[str] = []
    seen: set[str] = set()
    for img in main.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        absolute = urljoin(base_url, src)
        if absolute not in seen:
            seen.add(absolute)
            img_urls.append(absolute)

    links = _extract_links(main, base_url)
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text, img_urls, links


def _extract_links(main, base_url: str) -> list[dict]:
    links: list[dict] = []
    seen: set[str] = set()
    for a in main.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "javascript:")):
            continue
        absolute = urljoin(base_url, href).split("#", 1)[0]
        if not absolute.startswith(("http://", "https://")) or absolute in seen:
            continue
        label = " ".join(a.get_text(" ", strip=True).split())[:40]
        if not label:
            continue
        seen.add(absolute)
        links.append({"url": absolute, "label": label})
        if len(links) >= MAX_LINKS:
            break
    return links


def _fetch_image(client, url: str) -> dict | None:
    try:
        r = _validated_get(client, url)
        from PIL import Image, ImageOps

        im = Image.open(io.BytesIO(r.content))
        if im.width < IMG_MIN_SOURCE or im.height < IMG_MIN_SOURCE:
            return None
        im = im.convert("L")
        im = ImageOps.autocontrast(im)
        im.thumbnail((IMG_MAX_W, IMG_MAX_H))
        if im.width < IMG_MIN_CONTAINER or im.height < IMG_MIN_CONTAINER:
            return None
        # Encode as RGB: the Even host converts to gray4 itself and standard
        # RGB PNG is the safest input for that path (greyscale-mode PNGs are
        # less commonly handled by image decoders on-device).
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="PNG")
        return {"data": base64.b64encode(buf.getvalue()).decode("ascii"),
                "width": im.width, "height": im.height}
    except Exception as e:
        log.debug("image fetch failed for %s: %s", url, e)
        return None
