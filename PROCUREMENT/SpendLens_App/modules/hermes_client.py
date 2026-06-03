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


SPENDLENS_CATEGORY_TO_HERMES = {
    "Cloud & Compute":          "Cloud & Infrastructure",
    "AI/ML APIs & Data":        "AI Foundation Labs",
    "IT Software & SaaS":       "SaaS & Dev Tools",
    "Telecom & Voice":          "Telecom",
    "Recruitment & HR":         "HR & Talent",
    "Professional Services":    "Professional Services",
    "Marketing & Campaigns":    "Marketing Tech",
    "Facilities & Office":      "Facilities",
    "Real Estate":              "Real Estate",
    "Hardware & Equipment":     "Semiconductors & Chips",
    "Travel & Expenses":        "Travel & Logistics",
}


class HermesClient:
    """Read/write client for Hermes market intelligence, shared via Upstash Redis."""

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
        if not ids:
            return []
        raws = self.r.mget(*[f"hermes:item:{item_id}" for item_id in ids])
        return [json.loads(r) for r in raws if r]

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

    def get_procurement_briefing(self, limit: int = 20, all_significant: bool = True) -> list[dict]:
        """
        Top significant procurement signals across all tracked suppliers.
        all_significant=True (default): include ALL signal types that Hermes marks as significant.
        all_significant=False: restrict to core procurement types (SUPPLY_CHAIN, EARNINGS, etc.)
        """
        keys = self.r.keys("hermes:item:*")
        items = []
        for key in keys[:500]:
            raw = self.r.get(key)
            if raw:
                item = json.loads(raw)
                if not item.get("is_significant"):
                    continue
                if not all_significant and item.get("signal_type") not in PROCUREMENT_SIGNALS:
                    continue
                items.append(item)
        items.sort(key=lambda x: (x.get("urgency","LOW") == "HIGH", x.get("published", "")), reverse=True)
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

    def register_vendor(self, vendor_name: str, category: str, spend_eur: float = 0,
                        country: str = None, source: str = "spendlens") -> bool:
        """
        Register a SpendLens vendor in Hermes watchlist so crawlers start covering it.
        Writes to hermes:watchlist:{slug} with metadata. Does NOT overwrite existing
        supplier signal lists — only ensures the vendor is known to Hermes.
        Returns True if newly registered, False if already existed.
        """
        slug = self._slug(vendor_name)
        watchlist_key = f"hermes:watchlist:{slug}"
        if self.r.exists(watchlist_key):
            return False
        hermes_category = SPENDLENS_CATEGORY_TO_HERMES.get(category, category)
        entry = {
            "name": vendor_name,
            "slug": slug,
            "category": hermes_category,
            "spend_eur": round(spend_eur, 2),
            "country": country or "",
            "source": source,
            "registered_at": __import__("datetime").datetime.utcnow().isoformat(),
        }
        self.r.set(watchlist_key, json.dumps(entry))
        self._slug_cache = None  # invalidate cache so new vendor is discoverable
        return True

    def push_vendor_list(self, vendors: list[dict]) -> dict:
        """
        Bulk-register a list of SpendLens vendors into Hermes watchlist.
        Each vendor dict must have: vendor_name, category.
        Optional: spend_eur, country.
        Returns {"registered": N, "already_tracked": M}.
        """
        new_count = 0
        existing_count = 0
        for v in vendors:
            is_new = self.register_vendor(
                vendor_name=v["vendor_name"],
                category=v.get("category", ""),
                spend_eur=v.get("spend_eur", 0),
                country=v.get("country", ""),
            )
            if is_new:
                new_count += 1
            else:
                existing_count += 1
        return {"registered": new_count, "already_tracked": existing_count}

    def get_vendor_intel(self, vendor_name: str, limit: int = 5) -> dict:
        """
        Return all available Hermes intelligence for a vendor — signals + watchlist status.
        Used to enrich SpendLens vendor profiles with live market data.
        """
        slug = self._resolve(vendor_name)
        tracked = slug is not None
        signals = self.get_signals(vendor_name, limit=limit, procurement_only=False) if tracked else []
        risk_flags = [s for s in signals if s.get("urgency") in ("HIGH", "MEDIUM") and s.get("is_significant")]
        return {
            "tracked_by_hermes": tracked,
            "hermes_slug": slug,
            "signal_count": len(signals),
            "risk_flags": len(risk_flags),
            "top_signals": [
                {
                    "title": s.get("title", "")[:120],
                    "signal_type": s.get("signal_type"),
                    "urgency": s.get("urgency"),
                    "published": s.get("published", "")[:10],
                    "significance_reason": s.get("significance_reason", "")[:150],
                    "url": s.get("url", ""),
                }
                for s in signals[:limit]
            ],
        }

    # ------------------------------------------------------------------
    # ZEUS intelligence — reads zeus:* keys written by the trading system
    # ------------------------------------------------------------------

    def get_zeus_macro(self) -> dict | None:
        """Latest macro snapshot from ZEUS (regime, VIX, sector momentum)."""
        try:
            raw = self.r.get("zeus:macro:latest")
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def get_zeus_decisions(self, limit: int = 20) -> list[dict]:
        """Recent ZEUS trade decisions — for Icarus AI feed."""
        try:
            ids = self.r.lrange("zeus:decisions:recent", 0, limit - 1)
            if not ids:
                return []
            raws = self.r.mget(*[f"zeus:decision:{tid}" for tid in ids])
            return [json.loads(r) for r in raws if r]
        except Exception:
            return []

    def get_zeus_supplier_risk(self, vendor_name: str) -> dict | None:
        """ZEUS/Hades compliance assessment for a specific supplier."""
        slug = self._slug(vendor_name)
        try:
            raw = self.r.get(f"zeus:supplier_risk:{slug}")
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def zeus_decisions_as_icarus_signals(self, limit: int = 20) -> list[dict]:
        """
        Convert ZEUS DecisionTraces into Icarus signal format so they appear
        in the SpendLens Icarus AI screen alongside Hermes signals.
        """
        decisions = self.get_zeus_decisions(limit=limit)
        signals = []
        for d in decisions:
            if not d.get("headline"):
                continue
            approved  = d.get("zeus_approved", False)
            placed    = d.get("trade_placed", False)
            pnl       = d.get("pnl_pct")
            reasoning = d.get("zeus_reasoning", "")

            if placed and pnl is not None:
                impact = "positive" if pnl > 0 else "negative"
            elif approved:
                impact = "positive"
            else:
                impact = "neutral"

            action = reasoning[:200] if reasoning else (
                f"ZEUS {'TRADED' if placed else 'APPROVED' if approved else 'REJECTED'} — "
                f"{d.get('kill_reason') or d.get('side','')}"
            )
            signals.append({
                "source":    f"ZEUS · {d.get('supplier', 'Market')}",
                "headline":  d.get("headline", "")[:200],
                "summary":   f"Category: {d.get('category')} | Regime: {d.get('trend_regime')} | VIX: {d.get('trend_vix')} | Confidence: {d.get('pattern_confidence', 0):.0%}",
                "category":  SIGNAL_TO_CATEGORY.get(
                                 d.get("category", "OTHER").upper().replace("_","").replace(" ","_"), "Professional Services"
                             ),
                "relevance": 9 if placed else (7 if approved else 5),
                "impact":    impact,
                "action":    action,
                "url":       "",
                "published": d.get("timestamp", "")[:10],
                "countries": [],
            })
        return signals

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
