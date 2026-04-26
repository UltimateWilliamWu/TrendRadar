# coding=utf-8
"""
Selective RSS article enrichment for high-value sources.

The goal is to keep token usage controlled:
- regular RSS items only contribute title + summary
- selected high-value sources may add a short article snippet
"""

import re
from html import unescape
from typing import Any, Dict, List, Optional

import requests


class RSSContentEnricher:
    """Fetch short snippets for a small allowlist of RSS sources."""

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }

    GENERIC_SECTION_PATTERNS = [
        r"<article\b[^>]*>(.*?)</article>",
        r"<main\b[^>]*>(.*?)</main>",
        r"<section\b[^>]*class=[\"'][^\"']*(?:article|content|body)[^\"']*[\"'][^>]*>(.*?)</section>",
        r"<div\b[^>]*class=[\"'][^\"']*(?:article|content|body|story|detail|post)[^\"']*[\"'][^>]*>(.*?)</div>",
    ]

    SOURCE_HINTS = {
        "fed-monetary-policy": {
            "type": "macro",
            "patterns": [
                r"<div\b[^>]*class=[\"'][^\"']*(?:col-xs-12 col-sm-8 col-md-8|article|content)[^\"']*[\"'][^>]*>(.*?)</div>",
            ],
        },
        "sec-press-releases": {
            "type": "regulatory",
            "patterns": [
                r"<div\b[^>]*class=[\"'][^\"']*(?:article-body|region-content|content)[^\"']*[\"'][^>]*>(.*?)</div>",
            ],
        },
        "yahoo-finance": {
            "type": "company",
            "patterns": [
                r"<div\b[^>]*class=[\"'][^\"']*(?:caas-body|article-body|body-wrap)[^\"']*[\"'][^>]*>(.*?)</div>",
            ],
        },
        "chinanews-finance": {
            "type": "macro",
            "patterns": [
                r"<div\b[^>]*class=[\"'][^\"']*(?:left_zw|content_desc|content)[^\"']*[\"'][^>]*>(.*?)</div>",
            ],
        },
        "nbs-latest": {"type": "macro", "patterns": []},
        "nbs-interpretation": {"type": "macro", "patterns": []},
    }

    def __init__(
        self,
        source_policies: Dict[str, Dict[str, Any]],
        timeout: int = 12,
        debug: bool = False,
    ):
        self.source_policies = source_policies
        self.timeout = timeout
        self.debug = debug
        self._cache: Dict[str, Dict[str, str]] = {}

    def classify_source(self, item: Dict[str, Any]) -> str:
        feed_id = item.get("feed_id", "")
        policy = self.source_policies.get(feed_id, {})
        if policy.get("type"):
            return str(policy["type"])
        return self.SOURCE_HINTS.get(feed_id, {}).get("type", "general")

    def enrich(self, item: Dict[str, Any]) -> Dict[str, str]:
        feed_id = item.get("feed_id", "")
        url = item.get("url", "")

        if not feed_id or not url:
            return {}

        if url in self._cache:
            return dict(self._cache[url])

        policy = self.source_policies.get(feed_id)
        if not policy or not policy.get("enabled", False):
            return {}

        result = {
            "source_type": self.classify_source(item),
            "snippet": "",
        }

        try:
            response = requests.get(
                url,
                headers=self.DEFAULT_HEADERS,
                timeout=policy.get("timeout", self.timeout),
            )
            response.raise_for_status()
            html_text = response.text or ""

            meta_description = self._extract_meta_description(html_text)
            body_text = self._extract_body_text(feed_id, html_text)

            snippet_max_chars = int(policy.get("snippet_max_chars", 420) or 420)
            snippet = body_text or meta_description
            if snippet:
                snippet = self._truncate_text(snippet, snippet_max_chars)
                result["snippet"] = snippet
        except Exception as exc:
            if self.debug:
                print(f"[AI] RSS enrichment failed for {feed_id}: {exc}")

        self._cache[url] = dict(result)
        return dict(result)

    def _extract_meta_description(self, html_text: str) -> str:
        patterns = [
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']og:description["\']',
            r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                text = self._clean_text(match.group(1))
                if len(text) >= 40:
                    return text
        return ""

    def _extract_body_text(self, feed_id: str, html_text: str) -> str:
        hint_patterns = self.SOURCE_HINTS.get(feed_id, {}).get("patterns", [])
        candidates: List[str] = []

        for pattern in hint_patterns + self.GENERIC_SECTION_PATTERNS:
            for match in re.finditer(pattern, html_text, flags=re.IGNORECASE | re.DOTALL):
                section_text = self._extract_paragraph_block(match.group(1))
                if section_text:
                    candidates.append(section_text)

        if not candidates:
            fallback = self._extract_paragraph_block(html_text)
            if fallback:
                candidates.append(fallback)

        if not candidates:
            return ""

        candidates.sort(key=len, reverse=True)
        return candidates[0]

    def _extract_paragraph_block(self, html_fragment: str) -> str:
        paragraphs = []
        for raw in re.findall(r"<p\b[^>]*>(.*?)</p>", html_fragment, flags=re.IGNORECASE | re.DOTALL):
            text = self._clean_text(raw)
            if self._is_useful_paragraph(text):
                paragraphs.append(text)

        if not paragraphs:
            text = self._clean_text(html_fragment)
            return text if len(text) >= 80 else ""

        merged = []
        total_len = 0
        for paragraph in paragraphs:
            if paragraph in merged:
                continue
            merged.append(paragraph)
            total_len += len(paragraph)
            if total_len >= 1200:
                break
        return " ".join(merged).strip()

    def _is_useful_paragraph(self, text: str) -> bool:
        if len(text) < 40:
            return False

        noise_markers = [
            "copyright",
            "all rights reserved",
            "subscribe",
            "newsletter",
            "click here",
            "相关阅读",
            "责任编辑",
            "分享至",
            "打印本页",
        ]
        lowered = text.lower()
        return not any(marker in lowered for marker in noise_markers)

    def _clean_text(self, value: str) -> str:
        text = re.sub(r"(?is)<(script|style|svg|noscript|header|footer|nav).*?>.*?</\1>", " ", value)
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</p>", "\n", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"[\r\t]+", " ", text)
        text = re.sub(r"\n+", "\n", text)
        text = re.sub(r"[ ]{2,}", " ", text)
        return text.strip()

    def _truncate_text(self, text: str, max_chars: int) -> str:
        if max_chars <= 0 or len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "..."
