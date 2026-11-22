"""The plain-words reason shown on each career card, built from templates in English, Hindi and Marathi.

This is the baseline the learner always gets, instantly and with no AI. An AI-written sentence may later replace
the English one (and its translations) only if it passes `acceptable_reason`. Hindi and Marathi templates are
DRAFTS for native-speaker review. Reasons never mention income, demand or any number.
"""
from __future__ import annotations

import re
from typing import Any

from app.services import catalog
from app.services.career_engine import Ranked

LANGS = ("en", "hi", "mr")

T: dict[str, dict[str, str]] = {
    "skills": {
        "en": "You told us you can do {skills}, and this path builds on that.",
        "hi": "आपने बताया कि आप {skills} कर सकते हैं, और यह राह उसी पर बनती है।",
        "mr": "तुम्ही सांगितलं की तुम्हाला {skills} येतं, आणि हा मार्ग त्यावरच उभा आहे.",
    },
    "related": {
        "en": "It is close to {skills}, which you can already do.",
        "hi": "यह {skills} के करीब है, जो आप पहले से कर सकते हैं।",
        "mr": "हे {skills} च्या जवळचं आहे, जे तुम्हाला आधीच येतं.",
    },
    "via": {
        "en": "It is close to {career}, which suits you well.",
        "hi": "यह {career} के करीब है, जो आपके लिए अच्छा बैठता है।",
        "mr": "हे {career} च्या जवळचं आहे, जे तुम्हाला चांगलं जमतं.",
    },
    "tile": {
        "en": "You said you like {family}.",
        "hi": "आपने कहा था कि आपको {family} पसंद है।",
        "mr": "तुम्ही सांगितलं होतं की तुम्हाला {family} आवडतं.",
    },
    "starter": {
        "en": "We did not find a skill to match yet, so this is a common place to start.",
        "hi": "हमें अभी कोई हुनर नहीं मिला, इसलिए यह शुरुआत की एक आम जगह है।",
        "mr": "आम्हाला अजून जुळणारं कौशल्य सापडलं नाही, म्हणून ही सुरुवातीची एक सामान्य जागा आहे.",
    },
    "earn_soon": {
        "en": "It can bring a first income soon.",
        "hi": "इससे जल्दी पहली कमाई हो सकती है।",
        "mr": "यातून लवकर पहिली कमाई होऊ शकते.",
    },
    "earn_more": {
        "en": "It has room to grow over time.",
        "hi": "इसमें आगे बढ़ने की गुंजाइश है।",
        "mr": "यात पुढे वाढण्यास वाव आहे.",
    },
    "near_home": {
        "en": "You can do it near home.",
        "hi": "आप इसे घर के पास कर सकते हैं।",
        "mr": "तुम्ही हे घराजवळ करू शकता.",
    },
    "govt_job": {
        "en": "It prepares you for government exams.",
        "hi": "यह आपको सरकारी परीक्षाओं के लिए तैयार करता है।",
        "mr": "हे तुम्हाला सरकारी परीक्षांसाठी तयार करतं.",
    },
    "own_business": {
        "en": "You can run it as your own business.",
        "hi": "आप इसे अपने खुद के काम के रूप में चला सकते हैं।",
        "mr": "तुम्ही हे स्वतःचा व्यवसाय म्हणून चालवू शकता.",
    },
    "fits": {
        "en": "It also fits your time, money and travel.",
        "hi": "यह आपके समय, पैसे और सफ़र के हिसाब से भी ठीक बैठता है।",
        "mr": "हे तुमच्या वेळेला, पैशांना आणि प्रवासालाही जुळतं.",
    },
}

SEP = {"en": " ", "hi": " ", "mr": " "}


def _names(ids: list[str], lang: str) -> str:
    by_id = {s["id"]: s["name"][lang] for s in catalog.skills()}
    names = [by_id[i] for i in ids if i in by_id][:3]
    return ", ".join(names)


def _family_name(family: str, lang: str) -> str:
    return next((c["name"][lang] for c in catalog.categories() if c["id"] == family), family)


def build_reason(ranked: Ranked, priority: str) -> dict[str, str]:
    """One or two sentences, in every language. `priority` is the learner's "what matters most" tap."""
    career = catalog.career(ranked.career_id)
    assert career is not None
    out: dict[str, str] = {}
    for lang in LANGS:
        parts: list[str] = []
        if ranked.matched:
            parts.append(T["skills"][lang].format(skills=_names(ranked.matched, lang)))
        elif ranked.related:
            parts.append(T["related"][lang].format(skills=_names(ranked.related, lang)))
        elif ranked.via:
            via = catalog.career(ranked.via)
            parts.append(T["via"][lang].format(career=via["name"][lang] if via else ranked.via))
        elif ranked.tile:
            parts.append(T["tile"][lang].format(family=_family_name(career["family"], lang)))
        else:
            parts.append(T["starter"][lang])
        if ranked.priority_fit and priority in T:
            parts.append(T[priority][lang])
        elif ranked.fits and (ranked.matched or ranked.related or ranked.via):
            parts.append(T["fits"][lang])
        out[lang] = SEP[lang].join(parts)
    return out


# ---------------------------------------------------------------------------
# Guard for AI-written sentences
# ---------------------------------------------------------------------------

_BANNED = re.compile(r"[0-9०-९₹%]|\b(rs|rupees?|lakh|crore|salary|salaries|per month|per day|guarantee[sd]?|demand|vacanc\w+)\b", re.IGNORECASE)


def acceptable_reason(text: Any) -> bool:
    """A model's sentence is used only if it is short, plain and makes no claim about money, demand or numbers."""
    if not isinstance(text, str):
        return False
    t = text.strip()
    return 20 <= len(t) <= 220 and "\n" not in t and _BANNED.search(t) is None
