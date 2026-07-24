"""OpenAI Responses API client for LinkedIn discovery.

LinkedIn has no public search API and blocks scraping, so this module
surfaces PUBLIC, indexed LinkedIn content (member posts under /posts/ and
LinkedIn articles under /pulse/) via the OpenAI web_search tool constrained
to linkedin.com. It reuses the OPENAI_API_KEY already configured for Reddit.

Limitations (by design, honest):
- Only public / search-indexed content — not the private feed.
- No reliable engagement metrics (reactions/comments are behind auth), so
  we do not fabricate them; engagement is left null.
"""

import json
import re
import sys
from typing import Any, Dict, List, Optional

from . import http

# Fallback models when the selected model isn't accessible (mirrors openai_reddit)
MODEL_FALLBACK_ORDER = ["gpt-4o", "gpt-4o-mini"]


def _log_error(msg: str):
    sys.stderr.write(f"[LINKEDIN ERROR] {msg}\n")
    sys.stderr.flush()


def _log_info(msg: str):
    sys.stderr.write(f"[LINKEDIN] {msg}\n")
    sys.stderr.flush()


def _is_model_access_error(error: http.HTTPError) -> bool:
    if error.status_code != 400 or not error.body:
        return False
    body_lower = error.body.lower()
    return any(phrase in body_lower for phrase in [
        "verified", "organization must be", "does not have access",
        "not available", "not found",
    ])


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

# Depth configurations: (min, max) posts to request
# Request MORE than needed since many get filtered by date
DEPTH_CONFIG = {
    "quick": (10, 18),
    "default": (20, 35),
    "deep": (45, 70),
}

LINKEDIN_SEARCH_PROMPT = """Find LinkedIn posts and LinkedIn articles about: {topic}

STEP 1: EXTRACT THE CORE SUBJECT
Get the MAIN NOUN/PRODUCT/TOPIC and drop filler words like "best", "top",
"tips", "practices", "features".

STEP 2: SEARCH BROADLY ON LINKEDIN
Search public LinkedIn content:
1. "[core subject] site:linkedin.com/posts"
2. "[core subject] site:linkedin.com/pulse"
3. "[core subject] linkedin"
Focus on substantive professional commentary, hot takes, and firsthand
practitioner posts — the kind of B2B opinion that drives discussion.

STEP 3: INCLUDE ALL MATCHES
- Include ALL relevant posts/articles about the core subject.
- Set date to "YYYY-MM-DD" if you can determine it, otherwise null.
- We verify dates and filter old content server-side, so return MORE rather
  than fewer — do NOT pre-filter aggressively.

REQUIRED: URLs must contain "linkedin.com/posts/" OR "linkedin.com/pulse/"
REJECT: linkedin.com/jobs, linkedin.com/company pages with no post body,
        login walls, and generic profile URLs.

Find {min_items}-{max_items} items.

Return ONLY valid JSON in this exact format, no other text:
{{
  "items": [
    {{
      "text": "Post/article excerpt (the substantive claim or take)",
      "url": "https://www.linkedin.com/posts/... or /pulse/...",
      "author": "Author name and/or headline if known, else empty",
      "date": "YYYY-MM-DD or null",
      "why_relevant": "Why this matters for the topic",
      "relevance": 0.85
    }}
  ]
}}

Rules:
- relevance is 0.0 to 1.0 (1.0 = highly relevant)
- date must be YYYY-MM-DD format or null
- Prefer posts with a clear point of view, not just link-drops."""


def _extract_core_subject(topic: str) -> str:
    """Extract core subject from a verbose query for retry (mirrors reddit)."""
    noise = ['best', 'top', 'how to', 'tips for', 'practices', 'features',
             'killer', 'guide', 'tutorial', 'recommendations', 'advice',
             'prompting', 'using', 'for', 'with', 'the', 'of', 'in', 'on']
    words = topic.lower().split()
    result = [w for w in words if w not in noise]
    return ' '.join(result[:3]) or topic


def search_linkedin(
    api_key: str,
    model: str,
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    mock_response: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Search LinkedIn public content via OpenAI Responses API web_search.

    Args mirror openai_reddit.search_reddit for consistency.
    Returns the raw API response.
    """
    if mock_response is not None:
        return mock_response

    min_items, max_items = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    timeout = 90 if depth == "quick" else 120 if depth == "default" else 180

    models_to_try = [model] + [m for m in MODEL_FALLBACK_ORDER if m != model]

    input_text = LINKEDIN_SEARCH_PROMPT.format(
        topic=topic,
        from_date=from_date,
        to_date=to_date,
        min_items=min_items,
        max_items=max_items,
    )

    last_error = None
    for current_model in models_to_try:
        payload = {
            "model": current_model,
            "tools": [
                {
                    "type": "web_search",
                    "filters": {
                        "allowed_domains": ["linkedin.com"]
                    }
                }
            ],
            "include": ["web_search_call.action.sources"],
            "input": input_text,
        }

        try:
            return http.post(OPENAI_RESPONSES_URL, payload, headers=headers, timeout=timeout)
        except http.HTTPError as e:
            last_error = e
            if _is_model_access_error(e):
                _log_info(f"Model {current_model} not accessible, trying fallback...")
                continue
            raise

    if last_error:
        _log_error(f"All models failed. Last error: {last_error}")
        raise last_error
    raise http.HTTPError("No models available")


def parse_linkedin_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse OpenAI response to extract LinkedIn items."""
    items = []

    if "error" in response and response["error"]:
        error = response["error"]
        err_msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        _log_error(f"OpenAI API error: {err_msg}")
        if http.DEBUG:
            _log_error(f"Full error response: {json.dumps(response, indent=2)[:1000]}")
        return items

    output_text = ""
    if "output" in response:
        output = response["output"]
        if isinstance(output, str):
            output_text = output
        elif isinstance(output, list):
            for item in output:
                if isinstance(item, dict):
                    if item.get("type") == "message":
                        content = item.get("content", [])
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "output_text":
                                output_text = c.get("text", "")
                                break
                    elif "text" in item:
                        output_text = item["text"]
                elif isinstance(item, str):
                    output_text = item
                if output_text:
                    break

    if not output_text and "choices" in response:
        for choice in response["choices"]:
            if "message" in choice:
                output_text = choice["message"].get("content", "")
                break

    if not output_text:
        return items

    json_match = re.search(r'\{[\s\S]*"items"[\s\S]*\}', output_text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            items = data.get("items", [])
        except json.JSONDecodeError:
            pass

    clean_items = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        url = item.get("url", "")
        if not url or "linkedin.com" not in url:
            continue
        # Keep only real post/article URLs
        if "/posts/" not in url and "/pulse/" not in url:
            continue

        clean_item = {
            "id": f"L{i+1}",
            "text": str(item.get("text", "")).strip()[:600],
            "url": url,
            "author": str(item.get("author", "")).strip(),
            "date": item.get("date"),
            "why_relevant": str(item.get("why_relevant", "")).strip(),
            "relevance": min(1.0, max(0.0, float(item.get("relevance", 0.5)))),
        }

        if clean_item["date"]:
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(clean_item["date"])):
                clean_item["date"] = None

        clean_items.append(clean_item)

    return clean_items


def filter_and_sort(items: List[Dict[str, Any]], from_date: str, to_date: str) -> List[Dict[str, Any]]:
    """Keep undated items and those within range; sort by relevance desc.

    Kept intentionally self-contained so LinkedIn support does not depend on
    the reddit/x-specific normalize/score/dedupe modules.
    """
    seen_urls = set()
    kept = []
    for it in items:
        url = it.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        d = it.get("date")
        if d and not (from_date <= str(d) <= to_date):
            continue
        kept.append(it)
    kept.sort(key=lambda x: x.get("relevance", 0.0), reverse=True)
    return kept
