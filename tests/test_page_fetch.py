"""Offline tests for page_fetch HTML extraction (no network)."""
from hermes_evenhub_bridge import page_fetch


SAMPLE_HTML = """
<html><head><title>  Sample Page  </title><style>body{}</style></head>
<body>
<nav><a href="/nav-link">Nav</a></nav>
<main>
  <h1>Heading</h1>
  <p>Body text with a <a href="/relative">relative link</a> and an
     <a href="https://other.example/abs">absolute link</a> and a
     <a href="https://other.example/abs#frag">fragment dupe</a> and an
     <a href="#anchor">anchor</a> and a
     <a href="mailto:x@example.com">mail</a> and an
     <a href="https://other.example/empty"><img src="pic.png"></a>.</p>
  <img src="/hero.png">
  <img src="/hero.png">
  <img src="data:image/png;base64,AAAA">
</main>
<footer><a href="/footer-link">Footer</a></footer>
</body></html>
"""


def test_extract_title_text_images_links():
    title, text, img_urls, links = page_fetch._extract(
        SAMPLE_HTML, "https://site.example/article/")
    assert title == "Sample Page"
    assert "Heading" in text and "Body text" in text
    # nav/footer are stripped from both text and links
    assert "Nav" not in text
    assert all("nav-link" not in l["url"] and "footer-link" not in l["url"]
               for l in links)
    # images: resolved against base URL, deduped, data: URIs skipped
    # (document order: pic.png sits inside an anchor before hero.png)
    assert img_urls == ["https://site.example/article/pic.png",
                        "https://site.example/hero.png"]
    # links: absolute, fragment-stripped + deduped, anchors/mailto skipped,
    # empty-label (image-only) anchors skipped
    urls = [l["url"] for l in links]
    assert "https://site.example/relative" in urls
    assert urls.count("https://other.example/abs") == 1
    assert "https://other.example/empty" not in urls
    assert all(l["label"] for l in links)


def test_extract_caps_link_count():
    anchors = "".join(
        f'<a href="https://e.example/{i}">link {i}</a>' for i in range(40))
    _, _, _, links = page_fetch._extract(
        f"<html><body><main>{anchors}</main></body></html>",
        "https://e.example/")
    assert len(links) == page_fetch.MAX_LINKS


def test_fetch_page_rejects_non_http_schemes():
    import pytest
    with pytest.raises(ValueError):
        page_fetch.fetch_page("file:///etc/passwd")
    with pytest.raises(ValueError):
        page_fetch.fetch_page("ftp://example.com/x")


def test_ssrf_guard_blocks_non_public_hosts(monkeypatch):
    import pytest
    monkeypatch.delenv("EVENHUB_PAGE_FETCH_ALLOW_PRIVATE", raising=False)
    for url in [
        "http://127.0.0.1/admin",
        "http://192.168.1.1/",
        "http://10.0.0.5/x",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
    ]:
        with pytest.raises(ValueError):
            page_fetch._ensure_public_host(url)
    # Public IP literals pass without DNS.
    page_fetch._ensure_public_host("http://1.1.1.1/")


def test_ssrf_guard_env_opt_out(monkeypatch):
    monkeypatch.setenv("EVENHUB_PAGE_FETCH_ALLOW_PRIVATE", "1")
    page_fetch._ensure_public_host("http://192.168.1.1/")  # no raise
