"""
Influencer-brand matching engine for SponsorSync marketplace.
Scores influencer-brief compatibility using niche, audience, reach, and engagement signals.
"""
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BrandBrief:
    brief_id: str
    brand_name: str
    campaign_title: str
    niches: List[str]
    target_audience: List[str]
    min_followers: int
    max_followers: int
    min_engagement_rate: float
    budget_inr: float
    deliverables: List[str]
    preferred_platforms: List[str]
    content_guidelines: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class InfluencerProfile:
    influencer_id: str
    name: str
    handle: str
    platform: str
    followers: int
    engagement_rate: float
    niches: List[str]
    audience_demographics: Dict[str, Any]
    avg_reach: int
    past_brand_categories: List[str]
    content_quality_score: float
    response_rate: float
    avg_rate_inr: float
    bio: str = ""


@dataclass
class MatchScore:
    influencer_id: str
    brief_id: str
    total_score: float
    niche_score: float
    reach_score: float
    engagement_score: float
    audience_score: float
    platform_score: float
    budget_score: float
    explanation: str


class NicheScorer:
    """Computes semantic niche overlap between brief and influencer."""

    NICHE_SYNONYMS: Dict[str, Set[str]] = {
        "tech": {"technology", "gadgets", "software", "ai", "startup", "coding"},
        "fashion": {"style", "clothing", "ootd", "streetwear", "luxury"},
        "food": {"cooking", "recipes", "restaurant", "foodie", "culinary"},
        "fitness": {"gym", "workout", "health", "sports", "yoga", "wellness"},
        "travel": {"adventure", "tourism", "explore", "wanderlust", "backpacking"},
        "beauty": {"makeup", "skincare", "cosmetics", "grooming"},
        "finance": {"investing", "fintech", "money", "crypto", "economics"},
        "education": {"learning", "edtech", "courses", "study", "teaching"},
        "gaming": {"esports", "streaming", "twitch", "youtube gaming"},
        "parenting": {"mom", "dad", "kids", "family", "baby"},
    }

    def score(self, brief_niches: List[str], influencer_niches: List[str]) -> float:
        expanded_brief = self._expand(brief_niches)
        expanded_inf = self._expand(influencer_niches)
        if not expanded_brief or not expanded_inf:
            return 0.0
        overlap = len(expanded_brief & expanded_inf)
        union = len(expanded_brief | expanded_inf)
        return overlap / union if union else 0.0

    def _expand(self, niches: List[str]) -> Set[str]:
        result: Set[str] = set()
        for n in niches:
            n_lower = n.lower()
            result.add(n_lower)
            for canonical, synonyms in self.NICHE_SYNONYMS.items():
                if n_lower == canonical or n_lower in synonyms:
                    result.add(canonical)
                    result.update(synonyms)
        return result


class ReachScorer:
    """Scores how well the influencer's reach fits the brief's follower range."""

    def score(self, followers: int, min_followers: int, max_followers: int) -> float:
        if followers < min_followers:
            ratio = followers / min_followers
            return max(0.0, ratio)
        if followers > max_followers:
            overshoot = followers / max_followers
            return max(0.0, 1.0 - (overshoot - 1.0) * 0.3)
        center = (min_followers + max_followers) / 2
        width = (max_followers - min_followers) / 2
        if width == 0:
            return 1.0
        distance = abs(followers - center) / width
        return max(0.0, 1.0 - distance * 0.3)


class EngagementScorer:
    """Scores engagement rate relative to platform norms."""

    PLATFORM_BENCHMARKS: Dict[str, float] = {
        "instagram": 0.035,
        "youtube": 0.025,
        "tiktok": 0.06,
        "twitter": 0.015,
        "linkedin": 0.02,
        "facebook": 0.01,
    }
    PLATFORM_WEIGHT = 0.6

    def score(self, engagement_rate: float, min_engagement: float, platform: str) -> float:
        if engagement_rate < min_engagement:
            return max(0.0, engagement_rate / min_engagement * 0.5)
        benchmark = self.PLATFORM_BENCHMARKS.get(platform.lower(), 0.03)
        relative = engagement_rate / benchmark
        return min(1.0, relative * self.PLATFORM_WEIGHT + (1 - self.PLATFORM_WEIGHT))


class BudgetFitScorer:
    """Scores alignment between influencer rate and brand budget."""

    def score(self, influencer_rate: float, brief_budget: float) -> float:
        if influencer_rate <= 0 or brief_budget <= 0:
            return 0.5
        ratio = influencer_rate / brief_budget
        if ratio <= 0.5:
            return 0.8
        if ratio <= 1.0:
            return 1.0 - (ratio - 0.5) * 0.4
        if ratio <= 1.5:
            return 0.8 - (ratio - 1.0) * 0.6
        return 0.0


class InfluencerMatcher:
    """
    Scores and ranks influencers against a brand brief using multi-signal matching.
    """

    WEIGHTS = {
        "niche": 0.30,
        "reach": 0.20,
        "engagement": 0.20,
        "audience": 0.10,
        "platform": 0.10,
        "budget": 0.10,
    }

    def __init__(self):
        self.niche_scorer = NicheScorer()
        self.reach_scorer = ReachScorer()
        self.engagement_scorer = EngagementScorer()
        self.budget_scorer = BudgetFitScorer()

    def score(self, brief: BrandBrief, influencer: InfluencerProfile) -> MatchScore:
        niche_s = self.niche_scorer.score(brief.niches, influencer.niches)
        reach_s = self.reach_scorer.score(influencer.followers,
                                           brief.min_followers, brief.max_followers)
        engagement_s = self.engagement_scorer.score(influencer.engagement_rate,
                                                     brief.min_engagement_rate,
                                                     influencer.platform)
        platform_s = 1.0 if influencer.platform.lower() in [p.lower() for p in brief.preferred_platforms] else 0.3
        budget_s = self.budget_scorer.score(influencer.avg_rate_inr, brief.budget_inr)
        audience_s = influencer.content_quality_score

        total = (
            niche_s * self.WEIGHTS["niche"]
            + reach_s * self.WEIGHTS["reach"]
            + engagement_s * self.WEIGHTS["engagement"]
            + audience_s * self.WEIGHTS["audience"]
            + platform_s * self.WEIGHTS["platform"]
            + budget_s * self.WEIGHTS["budget"]
        )

        explanation = (
            f"Niche match {niche_s:.0%}, reach fit {reach_s:.0%}, "
            f"engagement {engagement_s:.0%}, platform {'match' if platform_s > 0.5 else 'mismatch'}, "
            f"budget fit {budget_s:.0%}."
        )

        return MatchScore(
            influencer_id=influencer.influencer_id,
            brief_id=brief.brief_id,
            total_score=round(total, 4),
            niche_score=round(niche_s, 4),
            reach_score=round(reach_s, 4),
            engagement_score=round(engagement_s, 4),
            audience_score=round(audience_s, 4),
            platform_score=round(platform_s, 4),
            budget_score=round(budget_s, 4),
            explanation=explanation,
        )

    def rank(self, brief: BrandBrief,
              influencers: List[InfluencerProfile],
              top_n: int = 10) -> List[Tuple[MatchScore, InfluencerProfile]]:
        scored = [(self.score(brief, inf), inf) for inf in influencers]
        scored.sort(key=lambda x: x[0].total_score, reverse=True)
        return scored[:top_n]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rng = np.random.default_rng(42)

    brief = BrandBrief(
        brief_id="brief_001",
        brand_name="TechGear India",
        campaign_title="Launch of Smart Watch Series 3",
        niches=["tech", "gadgets", "fitness"],
        target_audience=["18-35", "urban", "male", "female"],
        min_followers=50000,
        max_followers=500000,
        min_engagement_rate=0.03,
        budget_inr=150000,
        deliverables=["2 Instagram posts", "3 Stories", "1 YouTube video"],
        preferred_platforms=["instagram", "youtube"],
    )

    platforms = ["instagram", "youtube", "tiktok", "twitter"]
    niche_pool = [["tech", "gadgets"], ["fitness", "health"], ["fashion", "beauty"],
                   ["tech", "gaming"], ["travel", "lifestyle"], ["food", "cooking"]]

    influencers = []
    for i in range(20):
        influencers.append(InfluencerProfile(
            influencer_id=f"inf_{i:03d}",
            name=f"Influencer {i}",
            handle=f"@handle_{i}",
            platform=platforms[rng.integers(0, len(platforms))],
            followers=int(rng.integers(10000, 800000)),
            engagement_rate=float(rng.uniform(0.01, 0.12)),
            niches=niche_pool[rng.integers(0, len(niche_pool))],
            audience_demographics={"18-35": 0.65, "35-50": 0.25},
            avg_reach=int(rng.integers(5000, 200000)),
            past_brand_categories=["tech", "consumer"],
            content_quality_score=float(rng.uniform(0.5, 1.0)),
            response_rate=float(rng.uniform(0.6, 1.0)),
            avg_rate_inr=float(rng.integers(20000, 300000)),
        ))

    matcher = InfluencerMatcher()
    ranked = matcher.rank(brief, influencers, top_n=5)

    print(f"Top 5 matches for brief: {brief.campaign_title}\n")
    for i, (score, inf) in enumerate(ranked, 1):
        print(f"{i}. {inf.name} (@{inf.handle}) | {inf.platform} | "
              f"{inf.followers:,} followers | ER={inf.engagement_rate:.1%}")
        print(f"   Score: {score.total_score:.3f} | {score.explanation}")
