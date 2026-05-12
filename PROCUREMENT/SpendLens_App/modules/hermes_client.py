"""
Hermes Client — read-only access to Hermes market intelligence from SpendLens.
Connects to the shared Upstash Redis instance using the same credentials as Hermes.
Requires UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN in .env.
"""

import os
import json
from difflib import get_close_matches
from upstash_redis import Redis

PROCUREMENT_SIGNALS = {
    "SUPPLY_CHAIN",
    "PRICING_CHANGE",
    "EARNINGS",
    "REGULATORY",
    "ACQUISITION",
    "LAYOFFS_HIRING",
}

# Maps Hermes signal types to SpendLens spend categories
SIGNAL_TO_CATEGORY = {
    "SUPPLY_CHAIN":    "Hardware & Equipment",
    "PRICING_CHANGE":  "Cloud & Compute",
    "EARNINGS":        "Professional Services",
    "REGULATORY":      "Professional Services",
    "ACQUISITION":     "Cloud & Compute",
    "LAYOFFS_HIRING":  "Recruitment & HR",
    "FUNDING":         "AI/ML APIs & Data",
    "PRODUCT_RELEASE": "Cloud & Compute",
    "PARTNERSHIP":     "Professional Services",
    "RESEARCH_PAPER":  "AI/ML APIs & Data",
    "OTHER":           "Professional Services",
}

SIGNAL_TO_IMPACT = {
    "SUPPLY_CHAIN":    "negative",
    "PRICING_CHANGE":  "negative",
    "EARNINGS":        "neutral",
    "REGULATORY":      "negative",
    "ACQUISITION":     "neutral",
    "LAYOFFS_HIRING":  "neutral",
    "FUNDING":         "positive",
    "PRODUCT_RELEASE": "positive",
    "PARTNERSHIP":     "positive",
    "RESEARCH_PAPER":  "positive",
    "OTHER":           "neutral",
}

URGENCY_TO_RELEVANCE = {"HIGH": 9, "MEDIUM": 7, "LOW": 5}


class HermesClient:
    """Read-only client for querying Hermes market intelligence from SpendLens."""

    def __init__(self):
        self.r = Redis(
            url=os.environ["UPSTASH_REDIS_REST_URL"],
            token=os.environ["UPSTASH_REDIS_REST_TOKEN"],
        )
        self._slug_cache = None

    def _slug(self, name: str) -> str:
        return name.lower().strip().replace(" ", "_").replace("-", "_").replace(".", "_")

    def _known_slugs(self) -> list[str]:
        if self._slug_cache is None:
            keys = self.r.keys("hermes:supplier:*")
            self._slug_cache = [k.replace("hermes:supplier:", "") for k in keys]
        return self._slug_cache

    def _resolve(self, vendor_name: str) -> str | None:
        direct = self._slug(vendor_name)
        if self.r.exists(f"hermes:supplier:{direct}"):
            return direct
        known = self._known_slugs()
        matches = get_close_matches(direct, known, n=1, cutoff=0.6)
        return matches[0] if matches else None

    def _fetch_items(self, slug: str, limit: int) -> list[dict]:
        ids = self.r.lrange(f"hermes:supplier:{slug}", 0, limit - 1)
        items = []
        for item_id in ids:
            raw = self.r.get(f"hermes:item:{item_id}")
            if raw:
                items.append(json.loads(raw))
        return items

    def get_signals(self, vendor_name: str, limit: int = 10, procurement_only: bool = True) -> list[dict]:
        slug = self._resolve(vendor_name)
        if not slug:
            return []
        items = self._fetch_items(slug, limit)
        if procurement_only:
            items = [i for i in items if i.get("signal_type") in PROCUREMENT_SIGNALS]
        return items

    def get_risk_flags(self, vendor_name: str) -> list[dict]:
        items = self.get_signals(vendor_name, limit=20, procurement_only=True)
        return [i for i in items if i.get("is_significant") and i.get("urgency") in ("HIGH", "MEDIUM")]

    def get_procurement_briefing(self, limit: int = 20) -> list[dict]:
        """Top significant procurement signals across all tracked suppliers."""
        keys = self.r.keys("hermes:item:*")
        items = []
        for key in keys[:300]:
            raw = self.r.get(key)
            if raw:
                item = json.loads(raw)
                if item.get("is_significant") and item.get("signal_type") in PROCUREMENT_SIGNALS:
                    items.append(item)
        items.sort(key=lambda x: x.get("published", ""), reverse=True)
        return items[:limit]

    def enrich_vendor_list(self, vendor_names: list[str]) -> dict[str, dict]:
        """Bulk risk enrichment for a list of SpendLens vendor names."""
        result = {}
        for name in vendor_names:
            slug = self._resolve(name)
            if not slug:
                result[name] = {"tracked": False, "risk_level": "UNKNOWN", "signal_count": 0, "signals": []}
                continue
            signals = self.get_risk_flags(name)
            if any(s.get("urgency") == "HIGH" for s in signals):
                risk = "HIGH"
            elif signals:
                risk = "MEDIUM"
            else:
                risk = "LOW"
            result[name] = {
                "tracked": True,
                "hermes_slug": slug,
                "risk_level": risk,
                "signal_count": len(signals),
                "top_signal": signals[0] if signals else None,
                "signals": signals,
            }
        return result

    def to_icarus_signals(self, hermes_items: list[dict]) -> list[dict]:
        """
        Convert Hermes items to Icarus signal format so they can be
        injected directly into the Icarus signal pipeline and SQLite store.
        """
        signals = []
        for item in hermes_items:
            signal_type = item.get("signal_type", "OTHER")
            urgency = item.get("urgency", "LOW")
            reason = item.get("significance_reason", "")
            signals.append({
                "source":     f"Hermes · {item.get('supplier', '')}",
                "headline":   item.get("title", "")[:200],
                "summary":    reason or item.get("summary", "")[:300],
                "category":   SIGNAL_TO_CATEGORY.get(signal_type, "Professional Services"),
                "relevance":  URGENCY_TO_RELEVANCE.get(urgency, 5),
                "impact":     SIGNAL_TO_IMPACT.get(signal_type, "neutral"),
                "action":     reason[:200] if reason else f"Monitor {item.get('supplier','')} — {signal_type}",
                "url":        item.get("url", ""),
                "published":  item.get("published", "")[:10],
                "countries":  [],
            })
        return signals
