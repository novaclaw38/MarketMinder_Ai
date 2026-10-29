"""
Hard guardrails for the autonomous venture engine.
These are enforced in code; agents cannot waive them and no human approval is needed or consulted.
"""

import re
from typing import Any, Dict, Tuple

MIN_PRICE_CENTS = 300
MAX_PRICE_CENTS = 20_000

# Categories the engine will never launch (illegal, regulated, or harmful by default)
FORBIDDEN_TERMS = [
    r"\bgambl", r"\bbetting\b", r"\bcasino", r"\bporn", r"\badult\b", r"\bescort",
    r"\bcrypto (signal|trading|pump)", r"\bforex signal", r"\binvestment advice", r"\bfinancial advice",
    r"\bmedical advice", r"\bdiagnos", r"\blegal advice", r"\bweight loss", r"\bsupplement",
    r"\bfake (review|testimonial|follower)", r"\bscrap\w* (emails?|phone|personal)", r"\blead list",
    r"\bspam", r"\bcold (email|dm|outreach)", r"\bessay writing", r"\bhomework", r"\bimperson",
    r"\bget[- ]rich", r"\bmlm\b", r"\bpyramid", r"\bhack", r"\bcracked?\b", r"\bcounterfeit",
]

# What agents may do. Anything else is rejected, including money movement and unsolicited contact.
ALLOWED_ACTIONS = {"research", "create_product", "publish_article", "review_content", "spawn_agent", "log"}


def screen_text(text: str) -> Tuple[bool, str]:
    lowered = text.lower()
    for pattern in FORBIDDEN_TERMS:
        if re.search(pattern, lowered):
            return False, f"matches forbidden category: {pattern}"
    return True, ""


def screen_idea(idea: Dict[str, Any]) -> Tuple[bool, str]:
    required = ["name", "thesis", "audience", "product_title", "price_cents"]
    missing = [k for k in required if not idea.get(k)]
    if missing:
        return False, f"missing fields: {', '.join(missing)}"
    price = idea["price_cents"]
    if not isinstance(price, int) or not MIN_PRICE_CENTS <= price <= MAX_PRICE_CENTS:
        return False, "price outside allowed range"
    return screen_text(" ".join(str(idea[k]) for k in required))


def action_allowed(action: str) -> bool:
    return action in ALLOWED_ACTIONS
