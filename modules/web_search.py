"""Parse spoken search requests before handing real topics to the provider."""
import re
from urllib.parse import urlsplit


_SEARCH_REQUEST = re.compile(
    r"^\s*(?:(?:please|tolong|coba|bisa|boleh|kamu)\s+|"
    r"(?:can|could|would|will)\s+you\s+|(?:bisakah|bolehkah)\s+(?:kamu\s+)?)*"
    r"(?:look (?:on (?:the )?internet|online)|"
    r"search(?: (?:the )?(?:internet|web))?|look up|find me|google|"
    r"browse (?:the )?(?:internet|web)|carikan|cari(?: di (?:internet|web))?)"
    r"\b(?P<query>.*)$", re.I,
)


def clean_query(query):
    query = re.sub(r"\s+", " ", str(query)).strip(" \t\r\n.!?,:;\"'“”‘’")
    query = re.sub(r"^(?:for|about|tentang|untuk)\b\s*", "", query, flags=re.I).strip(" .!?,:;")
    return query if any(char.isalnum() for char in query) else ""


def search_request(text):
    """None means ordinary chat; an empty string means 'ask for a topic'."""
    match = _SEARCH_REQUEST.match(text)
    return clean_query(match["query"]) if match else None


def search_web(query, language="en"):
    query = clean_query(query)
    if not query:
        return {"type": "search_clarification"}
    errors, sources = [], []
    try:
        from ddgs import DDGS
        with DDGS(timeout=6) as search:
            # Yahoo works on networks where other providers are unreachable.
            # Fall back to independent providers if it fails or has no evidence.
            for backend in ("yahoo", "google,duckduckgo,brave"):
                try:
                    results = list(search.text(query, region="id-id" if language == "id" else "us-en",
                                               max_results=4, backend=backend))
                except Exception as error:
                    errors.append(str(error))
                    print(f"[SEARCH] {backend} failed: {error}")
                    continue
                for result in results:
                    snippet = (result.get("body") or result.get("snippet") or "").strip()
                    url = result.get("href") or result.get("url") or result.get("link") or ""
                    if snippet and urlsplit(url).scheme in {"http", "https"}:
                        sources.append({"title": result.get("title") or urlsplit(url).netloc,
                                        "snippet": snippet[:600], "url": url})
                if sources:
                    break
        if len(errors) == 2 and not sources:
            return {"type": "search_error", "message": " | ".join(errors)}
        return {"type": "search_results", "sources": sources}
    except Exception as error:
        print(f"[SEARCH] Provider unavailable: {error}")
        return {"type": "search_error", "message": str(error)}
