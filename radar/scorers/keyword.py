"""KeywordScorer: relevance by keyword hits on title+summary, blended with tier."""

from __future__ import annotations

from radar.models import Item, TopicSpec

# Source-tier weights, normalized to [0, 1].
TIER_WEIGHT: dict[str, float] = {
    "official": 1.0,
    "media": 0.7,
    "aggregator": 0.55,
    "self_media": 0.45,
    "entity": 0.4,
}
DEFAULT_TIER_WEIGHT = 0.3

KEYWORD_WEIGHT = 0.7
TIER_BLEND = 0.3


class KeywordScorer:
    def score(self, items: list[Item], topic: TopicSpec) -> list[Item]:
        keywords = topic.keywords or topic.prefilter_keywords
        lowered = [k.lower() for k in keywords]
        for item in items:
            tier_w = TIER_WEIGHT.get(item.tier, DEFAULT_TIER_WEIGHT)
            text = f"{item.title} {item.summary or ''}".lower()
            if lowered:
                hits = [kw for kw in keywords if kw.lower() in text]
                hit_rate = len(hits) / len(lowered)
                item.score = round(KEYWORD_WEIGHT * hit_rate + TIER_BLEND * tier_w, 4)
                item.score_reason = (
                    "hits: " + ", ".join(hits) if hits else "no keyword hits"
                )
            else:
                # No keywords configured -> fall back to tier weight only.
                item.score = round(tier_w, 4)
                item.score_reason = "tier-only (no keywords)"
        return items
