from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse
import httpx


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 ShortURLPreviewBot/1.0"
)


class _MetaHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_chunks: list[str] = []
        self.meta: Dict[str, str] = {}
        self.favicon: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        attr_map = {k.lower(): (v or "").strip() for k, v in attrs if k}

        if tag_lower == "title":
            self.in_title = True
        elif tag_lower == "meta":
            content = attr_map.get("content", "")
            if not content:
                return
            prop = attr_map.get("property", "").lower()
            name = attr_map.get("name", "").lower()
            if prop and prop not in self.meta:
                self.meta[prop] = content
            if name and name not in self.meta:
                self.meta[name] = content
        elif tag_lower == "link":
            rel = attr_map.get("rel", "").lower()
            href = attr_map.get("href", "")
            if href and ("icon" in rel) and not self.favicon:
                self.favicon = href

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_chunks.append(data)


def parse_html_metadata(html_text: str, base_url: str) -> Dict[str, Optional[str]]:
    parser = _MetaHTMLParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass

    parsed_url = urlparse(base_url)
    default_host = parsed_url.netloc or base_url
    default_favicon = f"{parsed_url.scheme}://{parsed_url.netloc}/favicon.ico" if parsed_url.scheme and parsed_url.netloc else None

    raw_title = (
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or "".join(parser.title_chunks).strip()
        or default_host
    )
    raw_desc = (
        parser.meta.get("og:description")
        or parser.meta.get("twitter:description")
        or parser.meta.get("description")
        or f"{default_host} 사이트로 연결되는 단축 링크입니다."
    )
    raw_image = (
        parser.meta.get("og:image")
        or parser.meta.get("twitter:image")
        or parser.meta.get("twitter:image:src")
    )

    meta_image = urljoin(base_url, raw_image) if raw_image else None
    favicon_url = urljoin(base_url, parser.favicon) if parser.favicon else default_favicon

    return {
        "meta_title": " ".join(raw_title.split())[:500] if raw_title else default_host,
        "meta_description": " ".join(raw_desc.split())[:2000] if raw_desc else None,
        "meta_image": meta_image,
        "favicon_url": favicon_url,
    }


def fetch_url_metadata(target_url: str, timeout: float = 4.0) -> Dict[str, Optional[str]]:
    parsed = urlparse(target_url)
    default_host = parsed.netloc or target_url
    default_favicon = f"{parsed.scheme}://{parsed.netloc}/favicon.ico" if parsed.scheme and parsed.netloc else None

    fallback = {
        "meta_title": default_host,
        "meta_description": f"{default_host} 사이트로 이동하는 단축 링크입니다.",
        "meta_image": None,
        "favicon_url": default_favicon,
        "meta_updated_at": datetime.now(timezone.utc),
    }

    if parsed.scheme not in ("http", "https"):
        return fallback

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        ) as client:
            resp = client.get(target_url)
            content_type = resp.headers.get("content-type", "").lower()
            if resp.status_code < 400 and ("html" in content_type or not content_type):
                html_snippet = resp.text[:150_000]
                extracted = parse_html_metadata(html_snippet, str(resp.url))
                extracted["meta_updated_at"] = datetime.now(timezone.utc)
                return extracted
    except Exception:
        pass

    return fallback
