"""Tavily Search API client."""

import json
import sys
from typing import Any, Dict, List, Optional
from datetime import datetime

from . import http

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def _log_error(msg: str):
    """Log error to stderr."""
    sys.stderr.write(f"[TAVILY ERROR] {msg}\n")
    sys.stderr.flush()


def search(
    api_key: str,
    query: str,
    search_depth: str = "advanced",
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    max_results: int = 20,
    days: int = 30,
) -> Dict[str, Any]:
    """Execute a search using Tavily API.

    Args:
        api_key: Tavily API key
        query: Search query
        search_depth: 'basic' or 'advanced' (defaults to 'advanced')
        include_domains: List of domains to include
        exclude_domains: List of domains to exclude
        max_results: Maximum results to return
        days: Number of days back to search (0 for no limit)

    Returns:
        Raw API response
    """
    headers = {
        "Content-Type": "application/json",
    }

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": search_depth,
        "include_images": False,
        "include_answer": False,
        "max_results": max_results,
    }

    if include_domains:
        payload["include_domains"] = include_domains
    
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains
        
    if days > 0:
        payload["days"] = days
        payload["topic"] = "news" # Required for days parameter often, implies recency

    return http.post(TAVILY_SEARCH_URL, payload, headers=headers)


def search_reddit(
    api_key: str,
    topic: str,
    days: int = 30,
    max_results: int = 50,
) -> Dict[str, Any]:
    """Specialized search for Reddit threads.
    
    Args:
        api_key: Tavily API key
        topic: Topic to search for
        days: content age in days
        max_results: max items to return
        
    Returns:
        Raw API response
    """
    # Construct a query that targets Reddit specifically
    # but also use include_domains for safety
    query = f"{topic} site:reddit.com"
    
    return search(
        api_key=api_key,
        query=query,
        include_domains=["reddit.com"],
        max_results=max_results,
        days=days
    )


def parse_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse Tavily response to standard item format.

    Args:
        response: Raw API response

    Returns:
        List of item dicts
    """
    items = []

    # Check for API errors
    if "error" in response:
        _log_error(f"API error: {response['error']}")
        return items
        
    results = response.get("results", [])
    
    for i, item in enumerate(results):
        if not isinstance(item, dict):
            continue

        clean_item = {
            "title": str(item.get("title", "")).strip(),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
            "date": item.get("published_date"),
            "score": item.get("score"),
            # Normalized fields
            "snippet": item.get("content", ""),
        }
        
        # Try to clean up date if present
        # Tavily dates are often ISO strings
        if clean_item["date"]:
            try:
                dt = datetime.fromisoformat(clean_item["date"].replace('Z', '+00:00'))
                clean_item["date"] = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                # keep original or set None, usually safe to keep original if it looks like a date
                pass

        items.append(clean_item)

    return items


def parse_reddit_items(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse Tavily response specifically for Reddit items.
    
    Adapts Tavily output to the schema expected by the rest of the app for Reddit items.
    """
    raw_items = parse_response(response)
    clean_items = []
    
    for i, item in enumerate(raw_items):
        url = item.get("url", "")
        if "reddit.com/r/" not in url or "/comments/" not in url:
            continue
            
        parts = url.split("/r/")
        subreddit = parts[1].split("/")[0] if len(parts) > 1 else ""
        
        clean_item = {
            "id": f"R{i+1}",
            "title": item.get("title", ""),
            "url": url,
            "subreddit": subreddit,
            "date": item.get("date"),
            "why_relevant": item.get("content", "")[:200] + "...",
            "relevance": item.get("score", 0.8), # Tavily score is relevance
        }
        clean_items.append(clean_item)
        
    return clean_items
