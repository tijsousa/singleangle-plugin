#!/usr/bin/env python3
"""
singleangle-research - Research a topic across Reddit + X + Web and output
structured research for Claude to convert into a single-angle post brief.

This is the research engine only. Claude Code reads the output and
runs the six-lens angle generator, then assembles the single-post
ingredient pack using the SKILL.md instructions.

Usage:
    python3 singleangle-research.py <topic> [options]

Options:
    --mock              Use fixtures instead of real API calls
    --emit=MODE         Output mode: compact|json|md (default: compact)
    --sources=MODE      Source selection: auto|reddit|x|both (default: auto)
    --quick             Faster research with fewer sources
    --deep              Comprehensive research with more sources
    --days=N            Look back N days (1-30, default: 30)
    --debug             Enable verbose debug logging
    --check             Check API key status and exit
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Add lib to path
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from lib import (
    dates,
    dedupe,
    entity_extract,
    env,
    http,
    linkedin,
    models,
    normalize,
    openai_reddit,
    reddit_enrich,
    render,
    schema,
    score,
    ui,
    xai_x,
)
# Bird CLI is optional — only import if available
try:
    from lib import bird_x
except Exception:
    bird_x = None

def load_fixture(name: str) -> dict:
    fixture_path = SCRIPT_DIR.parent / "fixtures" / name
    if fixture_path.exists():
        with open(fixture_path) as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# Research functions
# ---------------------------------------------------------------------------

def _search_reddit(topic, config, selected_models, from_date, to_date, depth, mock):
    raw_openai = None
    reddit_error = None

    if mock:
        raw_openai = load_fixture("openai_sample.json")
    else:
        try:
            raw_openai = openai_reddit.search_reddit(
                config["OPENAI_API_KEY"],
                selected_models["openai"],
                topic,
                from_date, to_date,
                depth=depth,
            )
        except http.HTTPError as e:
            raw_openai = {"error": str(e)}
            reddit_error = f"API error: {e}"
        except Exception as e:
            raw_openai = {"error": str(e)}
            reddit_error = f"{type(e).__name__}: {e}"

    reddit_items = openai_reddit.parse_reddit_response(raw_openai or {})

    # Retry with simpler query if few results
    if len(reddit_items) < 5 and not mock and not reddit_error:
        core = openai_reddit._extract_core_subject(topic)
        if core.lower() != topic.lower():
            try:
                retry_raw = openai_reddit.search_reddit(
                    config["OPENAI_API_KEY"],
                    selected_models["openai"],
                    core,
                    from_date, to_date,
                    depth=depth,
                )
                retry_items = openai_reddit.parse_reddit_response(retry_raw)
                existing_urls = {item.get("url") for item in reddit_items}
                for item in retry_items:
                    if item.get("url") not in existing_urls:
                        reddit_items.append(item)
            except Exception:
                pass

    # Subreddit-targeted fallback
    if len(reddit_items) < 3 and not mock and not reddit_error:
        sub_query = openai_reddit._build_subreddit_query(topic)
        try:
            sub_raw = openai_reddit.search_reddit(
                config["OPENAI_API_KEY"],
                selected_models["openai"],
                sub_query,
                from_date, to_date,
                depth=depth,
            )
            sub_items = openai_reddit.parse_reddit_response(sub_raw)
            existing_urls = {item.get("url") for item in reddit_items}
            for item in sub_items:
                if item.get("url") not in existing_urls:
                    reddit_items.append(item)
        except Exception:
            pass

    return reddit_items, raw_openai, reddit_error


def _search_x(topic, config, selected_models, from_date, to_date, depth, mock, x_source="xai"):
    raw_response = None
    x_error = None

    if mock:
        raw_response = load_fixture("xai_sample.json")
        x_items = xai_x.parse_x_response(raw_response or {})
        return x_items, raw_response, x_error

    if x_source == "bird":
        try:
            raw_response = bird_x.search_x(topic, from_date, to_date, depth=depth)
        except Exception as e:
            raw_response = {"error": str(e)}
            x_error = f"{type(e).__name__}: {e}"
        x_items = bird_x.parse_bird_response(raw_response or {})
        if raw_response and isinstance(raw_response, dict) and raw_response.get("error") and not x_error:
            x_error = raw_response["error"]
        return x_items, raw_response, x_error

    try:
        raw_response = xai_x.search_x(
            config["XAI_API_KEY"],
            selected_models["xai"],
            topic,
            from_date, to_date,
            depth=depth,
        )
    except http.HTTPError as e:
        raw_response = {"error": str(e)}
        x_error = f"API error: {e}"
    except Exception as e:
        raw_response = {"error": str(e)}
        x_error = f"{type(e).__name__}: {e}"

    x_items = xai_x.parse_x_response(raw_response or {})
    return x_items, raw_response, x_error


def _search_linkedin(topic, config, selected_models, from_date, to_date, depth, mock):
    """Search public LinkedIn content via OpenAI web_search (reuses OpenAI key)."""
    raw_response = None
    li_error = None

    if mock:
        return [], None, None

    try:
        raw_response = linkedin.search_linkedin(
            config["OPENAI_API_KEY"],
            selected_models["openai"],
            topic,
            from_date, to_date,
            depth=depth,
        )
    except http.HTTPError as e:
        raw_response = {"error": str(e)}
        li_error = f"API error: {e}"
    except Exception as e:
        raw_response = {"error": str(e)}
        li_error = f"{type(e).__name__}: {e}"

    li_items = linkedin.parse_linkedin_response(raw_response or {})

    # Retry with core subject if thin
    if len(li_items) < 3 and not li_error:
        core = linkedin._extract_core_subject(topic)
        if core.lower() != topic.lower():
            try:
                retry_raw = linkedin.search_linkedin(
                    config["OPENAI_API_KEY"],
                    selected_models["openai"],
                    core,
                    from_date, to_date,
                    depth=depth,
                )
                retry_items = linkedin.parse_linkedin_response(retry_raw)
                existing = {it.get("url") for it in li_items}
                for it in retry_items:
                    if it.get("url") not in existing:
                        li_items.append(it)
            except Exception:
                pass

    return li_items, raw_response, li_error


def _run_supplemental(topic, reddit_items, x_items, from_date, to_date, depth, x_source, progress=None):
    max_handles = 3 if depth == "default" else 5
    max_subs = 3 if depth == "default" else 5
    count_per = 3 if depth == "default" else 5

    entities = entity_extract.extract_entities(
        reddit_items, x_items,
        max_handles=max_handles,
        max_subreddits=max_subs,
    )

    has_handles = entities["x_handles"] and x_source == "bird"
    has_subs = entities["reddit_subreddits"]

    if not has_handles and not has_subs:
        return [], []

    existing_urls = set()
    for item in reddit_items:
        existing_urls.add(item.get("url", ""))
    for item in x_items:
        existing_urls.add(item.get("url", ""))

    supplemental_reddit = []
    supplemental_x = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        reddit_future = None
        x_future = None

        if has_subs:
            reddit_future = executor.submit(
                openai_reddit.search_reddit,
                entities["reddit_subreddits"],
                topic, from_date, to_date, count_per,
            )
        if has_handles:
            x_future = executor.submit(
                bird_x.search_handles,
                entities["x_handles"],
                topic, from_date, count_per,
            )

        if reddit_future:
            try:
                raw_reddit = reddit_future.result()
                supplemental_reddit = [
                    item for item in raw_reddit
                    if item.get("url", "") not in existing_urls
                ]
            except Exception as e:
                sys.stderr.write(f"[Phase 2] Supplemental Reddit error: {e}\n")

        if x_future:
            try:
                raw_x = x_future.result()
                supplemental_x = [
                    item for item in raw_x
                    if item.get("url", "") not in existing_urls
                ]
            except Exception as e:
                sys.stderr.write(f"[Phase 2] Supplemental X error: {e}\n")

    return supplemental_reddit, supplemental_x


def run_research(topic, sources, config, selected_models, from_date, to_date,
                 depth="default", mock=False, progress=None, x_source="xai",
                 run_linkedin=False):
    reddit_items = []
    x_items = []
    linkedin_items = []
    raw_openai = None
    raw_xai = None
    raw_linkedin = None
    raw_reddit_enriched = []
    reddit_error = None
    x_error = None
    linkedin_error = None

    web_needed = sources in ("all", "web", "reddit-web", "x-web")

    if sources == "web":
        if progress:
            progress.start_web_only()
            progress.end_web_only()
        return (reddit_items, x_items, linkedin_items, True, raw_openai, raw_xai,
                raw_linkedin, raw_reddit_enriched, reddit_error, x_error, linkedin_error)

    run_reddit = sources in ("both", "reddit", "all", "reddit-web")
    run_x = sources in ("both", "x", "all", "x-web")

    with ThreadPoolExecutor(max_workers=3) as executor:
        reddit_future = None
        x_future = None
        linkedin_future = None

        if run_reddit:
            if progress:
                progress.start_reddit()
            reddit_future = executor.submit(
                _search_reddit, topic, config, selected_models,
                from_date, to_date, depth, mock
            )
        if run_x:
            if progress:
                progress.start_x()
            x_future = executor.submit(
                _search_x, topic, config, selected_models,
                from_date, to_date, depth, mock, x_source
            )
        if run_linkedin:
            linkedin_future = executor.submit(
                _search_linkedin, topic, config, selected_models,
                from_date, to_date, depth, mock
            )

        if reddit_future:
            try:
                reddit_items, raw_openai, reddit_error = reddit_future.result()
                if reddit_error and progress:
                    progress.show_error(f"Reddit error: {reddit_error}")
            except Exception as e:
                reddit_error = f"{type(e).__name__}: {e}"
                if progress:
                    progress.show_error(f"Reddit error: {e}")
            if progress:
                progress.end_reddit(len(reddit_items))

        if x_future:
            try:
                x_items, raw_xai, x_error = x_future.result()
                if x_error and progress:
                    progress.show_error(f"X error: {x_error}")
            except Exception as e:
                x_error = f"{type(e).__name__}: {e}"
                if progress:
                    progress.show_error(f"X error: {e}")
            if progress:
                progress.end_x(len(x_items))

        if linkedin_future:
            try:
                linkedin_items, raw_linkedin, linkedin_error = linkedin_future.result()
                if linkedin_error and progress:
                    progress.show_error(f"LinkedIn error: {linkedin_error}")
            except Exception as e:
                linkedin_error = f"{type(e).__name__}: {e}"
                if progress:
                    progress.show_error(f"LinkedIn error: {e}")

    # Filter + sort LinkedIn items (self-contained; no reddit/x-specific deps)
    if linkedin_items:
        linkedin_items = linkedin.filter_and_sort(linkedin_items, from_date, to_date)

    # Enrich Reddit items
    if reddit_items:
        if progress:
            progress.start_reddit_enrich(1, len(reddit_items))
        for i, item in enumerate(reddit_items):
            if progress and i > 0:
                progress.update_reddit_enrich(i + 1, len(reddit_items))
            try:
                if mock:
                    mock_thread = load_fixture("reddit_thread_sample.json")
                    reddit_items[i] = reddit_enrich.enrich_reddit_item(item, mock_thread)
                else:
                    reddit_items[i] = reddit_enrich.enrich_reddit_item(item)
            except Exception as e:
                if progress:
                    progress.show_error(f"Enrich failed for {item.get('url', 'unknown')}: {e}")
            raw_reddit_enriched.append(reddit_items[i])
        if progress:
            progress.end_reddit_enrich()

    # Phase 2: Supplemental search
    if depth != "quick" and not mock and (reddit_items or x_items):
        sup_reddit, sup_x = _run_supplemental(
            topic, reddit_items, x_items,
            from_date, to_date, depth, x_source, progress,
        )
        if sup_reddit:
            reddit_items.extend(sup_reddit)
        if sup_x:
            x_items.extend(sup_x)

    return (reddit_items, x_items, linkedin_items, web_needed, raw_openai, raw_xai,
            raw_linkedin, raw_reddit_enriched, reddit_error, x_error, linkedin_error)


# ---------------------------------------------------------------------------
# Output: render research as a clean markdown doc for Claude to process
# ---------------------------------------------------------------------------

def render_research_md(topic, from_date, to_date, reddit_items, x_items, days, linkedin_items=None):
    """Render research results into a clean markdown document that Claude
    will read and convert into talking points."""

    linkedin_items = linkedin_items or []

    lines = [
        f"# Research Results: {topic}",
        f"**Date range:** {from_date} to {to_date} ({days} days)",
        f"**Reddit threads found:** {len(reddit_items)}",
        f"**X posts found:** {len(x_items)}",
        f"**LinkedIn posts found:** {len(linkedin_items)}",
        "",
        "---",
        "",
    ]

    # Reddit section
    if reddit_items:
        lines.append("## Reddit Discussions")
        lines.append("")
        for item in reddit_items:
            title = item.get("title") or item.get("text", "Untitled")
            url = item.get("url", "")
            subreddit = item.get("subreddit", "unknown")
            date = item.get("date", "unknown")
            relevance = item.get("relevance", 0)
            why = item.get("why_relevant", "")

            # Engagement metrics (from enrichment)
            upvotes = item.get("upvotes") or item.get("score", 0)
            comments = item.get("num_comments") or item.get("comment_count", 0)

            # Top comments (from enrichment)
            top_comments = item.get("top_comments", [])

            lines.append(f"### {title}")
            lines.append(f"**Subreddit:** r/{subreddit} | **Date:** {date} | **Upvotes:** {upvotes} | **Comments:** {comments}")
            if url:
                lines.append(f"**URL:** {url}")
            if why:
                lines.append(f"**Why relevant:** {why}")

            # Include top comments — these are gold for talking points
            if top_comments:
                lines.append("")
                lines.append("**Top comments:**")
                for comment in top_comments[:5]:
                    body = comment.get("body", "")
                    c_score = comment.get("score", 0)
                    if body:
                        # Truncate long comments
                        if len(body) > 500:
                            body = body[:500] + "..."
                        lines.append(f"- ({c_score} pts) {body}")

            lines.append("")
            lines.append("---")
            lines.append("")

    # X section
    if x_items:
        lines.append("## X/Twitter Posts")
        lines.append("")
        for item in x_items:
            text = item.get("text", "")
            url = item.get("url", "")
            author = item.get("author_handle", "unknown")
            date = item.get("date", "unknown")
            engagement = item.get("engagement") or {}
            likes = engagement.get("likes", 0) if isinstance(engagement, dict) else 0
            reposts = engagement.get("reposts", 0) if isinstance(engagement, dict) else 0

            lines.append(f"### @{author}")
            lines.append(f"**Date:** {date} | **Likes:** {likes} | **Reposts:** {reposts}")
            if url:
                lines.append(f"**URL:** {url}")
            lines.append("")
            lines.append(f"> {text}")
            lines.append("")
            lines.append("---")
            lines.append("")

    # LinkedIn section
    if linkedin_items:
        lines.append("## LinkedIn Posts & Articles")
        lines.append("")
        lines.append("*Public, search-indexed LinkedIn content. Engagement metrics are")
        lines.append("not available for LinkedIn (behind auth) and are intentionally omitted.*")
        lines.append("")
        for item in linkedin_items:
            text = item.get("text", "")
            url = item.get("url", "")
            author = item.get("author", "").strip() or "unknown"
            date = item.get("date", "unknown")
            why = item.get("why_relevant", "")
            kind = "Article" if "/pulse/" in url else "Post"

            lines.append(f"### {author}")
            lines.append(f"**Type:** {kind} | **Date:** {date}")
            if url:
                lines.append(f"**URL:** {url}")
            if why:
                lines.append(f"**Why relevant:** {why}")
            lines.append("")
            if text:
                lines.append(f"> {text}")
            lines.append("")
            lines.append("---")
            lines.append("")

    if not reddit_items and not x_items and not linkedin_items:
        lines.append("## No Results Found")
        lines.append("")
        lines.append("No relevant content was found for this topic in the specified time range.")
        lines.append("Consider broadening your topic or extending the date range.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Research a topic across Reddit + X for viral talking point extraction"
    )
    parser.add_argument("topic", nargs="?", help="Topic to research")
    parser.add_argument("--mock", action="store_true", help="Use fixtures")
    parser.add_argument(
        "--emit", choices=["compact", "json", "md"], default="compact",
        help="Output mode",
    )
    parser.add_argument(
        "--sources", choices=["auto", "reddit", "x", "both"], default="auto",
        help="Source selection",
    )
    parser.add_argument("--quick", action="store_true", help="Faster, fewer sources")
    parser.add_argument("--deep", action="store_true", help="Comprehensive research")
    parser.add_argument("--debug", action="store_true", help="Verbose debug logging")
    parser.add_argument("--include-web", action="store_true", help="Include web search")
    parser.add_argument("--no-linkedin", action="store_true",
                        help="Disable the LinkedIn source (on by default when OpenAI key is present)")
    parser.add_argument(
        "--days", type=int, default=30, choices=range(1, 31), metavar="N",
        help="Days to look back (1-30, default: 30)",
    )
    parser.add_argument("--check", action="store_true", help="Check API keys and exit")

    args = parser.parse_args()

    # Key check mode
    if args.check:
        config = env.get_config()
        available = env.get_available_sources(config)
        print("\n--- API Key Status ---")
        print(f"  OPENAI_API_KEY: {'✅ Found' if config.get('OPENAI_API_KEY') else '❌ Missing'}")
        print(f"  XAI_API_KEY:    {'✅ Found' if config.get('XAI_API_KEY') else '❌ Missing'}")

        # Check Bird
        try:
            x_status = env.get_x_source_status(config)
            if x_status["bird_installed"]:
                auth = "✅ Authenticated" if x_status["bird_authenticated"] else "❌ Not authenticated"
                print(f"  Bird CLI:       {auth}")
        except AttributeError:
            pass

        print(f"\n  Available sources: {available}")
        return

    if args.debug:
        os.environ["LAST30DAYS_DEBUG"] = "1"
        from lib import http as http_module
        http_module.DEBUG = True

    if args.quick and args.deep:
        print("Error: Cannot use both --quick and --deep", file=sys.stderr)
        sys.exit(1)

    depth = "quick" if args.quick else "deep" if args.deep else "default"

    if not args.topic:
        print("Error: Please provide a topic to research.", file=sys.stderr)
        print("Usage: python3 singleangle-research.py <topic> [options]", file=sys.stderr)
        sys.exit(1)

    # Load config
    config = env.get_config()

    # Auto-detect Bird
    try:
        x_source_status = env.get_x_source_status(config)
        x_source = x_source_status["source"]
    except AttributeError:
        x_source = "xai" if config.get("XAI_API_KEY") else None

    # Progress display
    progress = ui.ProgressDisplay(args.topic, show_banner=True)

    # Check available sources
    available = env.get_available_sources(config)
    if x_source == 'bird':
        if available == 'reddit':
            available = 'both'
        elif available == 'web':
            available = 'x'

    if args.mock:
        sources = "both" if args.sources == "auto" else args.sources
    else:
        sources, error = env.validate_sources(args.sources, available, args.include_web)
        if error:
            if "WebSearch fallback" in error:
                print(f"Note: {error}", file=sys.stderr)
            else:
                print(f"Error: {error}", file=sys.stderr)
                sys.exit(1)

    # Date range
    from_date, to_date = dates.get_date_range(args.days)

    # Missing keys promo
    missing_keys = env.get_missing_keys(config)
    if missing_keys != 'none':
        progress.show_promo(missing_keys)

    # Select models
    if args.mock:
        mock_openai_models = load_fixture("models_openai_sample.json").get("data", [])
        mock_xai_models = load_fixture("models_xai_sample.json").get("data", [])
        selected_models = models.get_models(
            {"OPENAI_API_KEY": "mock", "XAI_API_KEY": "mock", **config},
            mock_openai_models, mock_xai_models,
        )
    else:
        selected_models = models.get_models(config)

    # LinkedIn runs as an extra lane whenever the OpenAI key is present and we're
    # not in an X-only / web-only selection (it reuses the OpenAI web_search tool).
    run_linkedin = (
        not args.mock
        and not args.no_linkedin
        and bool(config.get("OPENAI_API_KEY"))
        and sources in ("both", "reddit", "all", "reddit-web")
    )
    if run_linkedin and progress:
        try:
            progress.show_error("LinkedIn: searching public posts & articles…")
        except Exception:
            pass

    # Run research
    (reddit_items, x_items, linkedin_items, web_needed, raw_openai, raw_xai,
     raw_linkedin, raw_reddit_enriched, reddit_error, x_error, linkedin_error) = run_research(
        args.topic, sources, config, selected_models,
        from_date, to_date, depth, args.mock, progress,
        x_source=x_source or "xai",
        run_linkedin=run_linkedin,
    )

    # Processing
    progress.start_processing()

    normalized_reddit = normalize.normalize_reddit_items(reddit_items, from_date, to_date)
    normalized_x = normalize.normalize_x_items(x_items, from_date, to_date)

    filtered_reddit = normalize.filter_by_date_range(normalized_reddit, from_date, to_date)
    filtered_x = normalize.filter_by_date_range(normalized_x, from_date, to_date)

    scored_reddit = score.score_reddit_items(filtered_reddit)
    scored_x = score.score_x_items(filtered_x)

    sorted_reddit = score.sort_items(scored_reddit)
    sorted_x = score.sort_items(scored_x)

    deduped_reddit = dedupe.dedupe_reddit(sorted_reddit)
    deduped_x = dedupe.dedupe_x(sorted_x)

    # Minimum result guarantee
    if not deduped_reddit and normalized_reddit:
        by_relevance = sorted(normalized_reddit, key=lambda item: item.relevance, reverse=True)
        deduped_reddit = by_relevance[:3]

    progress.end_processing()

    # Convert to dicts for our renderer
    reddit_dicts = [item.to_dict() if hasattr(item, 'to_dict') else item for item in deduped_reddit]
    x_dicts = [item.to_dict() if hasattr(item, 'to_dict') else item for item in deduped_x]

    # LinkedIn items are already plain dicts (self-contained lane)
    linkedin_dicts = linkedin_items or []

    # Render output
    research_md = render_research_md(
        args.topic, from_date, to_date, reddit_dicts, x_dicts, args.days,
        linkedin_items=linkedin_dicts,
    )

    # Save to file
    output_dir = Path.home() / ".local" / "share" / "singleangle" / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "research.md"
    output_path.write_text(research_md, encoding="utf-8")

    # Also save raw JSON for debugging
    raw_json_path = output_dir / "research.json"
    raw_json_path.write_text(json.dumps({
        "topic": args.topic,
        "from_date": from_date,
        "to_date": to_date,
        "reddit": reddit_dicts,
        "x": x_dicts,
        "linkedin": linkedin_dicts,
        "reddit_error": reddit_error,
        "x_error": x_error,
        "linkedin_error": linkedin_error,
    }, indent=2, default=str), encoding="utf-8")

    # Show completion
    print(f"\n✅ Research complete: {len(reddit_dicts)} Reddit threads + {len(x_dicts)} X posts + {len(linkedin_dicts)} LinkedIn posts")
    print(f"📄 Saved to: {output_path}")

    if web_needed:
        print("\n⚠️  WebSearch recommended for supplementary web sources.")
        print(f"   Topic: {args.topic}")
        print(f"   Date range: {from_date} to {to_date}")

    # Output based on emit mode
    if args.emit == "md":
        print(research_md)
    elif args.emit == "json":
        print(json.dumps({
            "topic": args.topic,
            "from_date": from_date,
            "to_date": to_date,
            "reddit_count": len(reddit_dicts),
            "x_count": len(x_dicts),
            "output_path": str(output_path),
        }, indent=2))
    else:
        # Compact mode — just confirm and let Claude read the file
        print(f"\nClaude: Read {output_path} and convert to talking points.")


if __name__ == "__main__":
    main()
