"""The evidence rule: a skill needs the learner's own words, matched by whole word."""
from __future__ import annotations

import pytest

from app.services import catalog, evidence

BY_ID = {s["id"]: s for s in catalog.skills()}


def supported(skill_id: str, text: str) -> bool:
    return evidence.has_evidence(BY_ID[skill_id], text)


@pytest.mark.parametrize(
    "skill_id, text",
    [
        ("handicraft", "I like painting"),
        ("handicraft", "I paint and draw"),
        ("sewing", "I stitched two blouses"),
        ("sewing", "tailoring is my dream"),
        ("baking", "I am baking cakes"),  # the e is dropped before -ing
        ("two_wheeler_repair", "I fix a two-wheeler"),  # hyphen is a space
        ("photography", "I take photographs"),
        ("sewing_machine_care", "I repaired our Sewing Machine"),
        ("sewing", "मैं सिलाई करती हूँ"),
        ("sewing", "मी कपडे शिवते"),
        ("sewing_machine_care", "मी शिलाई मशीन दुरुस्त करते"),
        ("handicraft", "मुझे पेंटिंग पसंद है"),
    ],
)
def test_the_learners_words_support_the_skill(skill_id, text):
    assert supported(skill_id, text)


@pytest.mark.parametrize(
    "skill_id, text",
    [
        ("mushroom_beekeeping", "I have been there"),  # "been" is not a bee
        ("poultry_care", "when and then"),  # "when" is not a hen
        ("garment_finishing", "I wear them often"),  # "them" is not a hem
        ("handicraft", "start the day early"),  # "start" is not art
        ("computer_basics", "I excel at maths"),
        ("gst_basics", "मुझे बिलकुल पता नहीं"),  # "बिलकुल" means "absolutely", not a bill
        ("bookkeeping", "मैं खाना खाता हूँ"),  # "खाता" here means "eats"
        ("motor_repair", "मैं मोटरसाइकिल चलाता हूँ"),  # a motorcycle is not a motor
        ("mushroom_beekeeping", "ते मधल्या वेळेत आले"),  # Marathi "मधल्या" means "in between"
        ("photography", "I like watching cricket"),
        ("tutoring", "I play with my friends"),
    ],
)
def test_everyday_words_are_not_evidence(skill_id, text):
    assert not supported(skill_id, text)


def test_every_skill_keeps_at_least_one_keyword_after_tightening():
    for s in catalog.skills():
        assert s["keywords"], s["id"]


def test_no_latin_keyword_is_a_one_or_two_letter_trap():
    for s in catalog.skills():
        for kw in s["keywords"]:
            if kw.isascii():
                assert len(kw) >= 3, (s["id"], kw)  # very short Latin keywords collide with ordinary words


@pytest.mark.parametrize(
    "text, expected",
    [
        ("I fix my friends mobile phones", True),  # fix + phone in one answer
        ("मैं दोस्तों के मोबाइल की स्क्रीन बदल देता हूँ", True),
        ("I take photos with my mobile", False),  # owning or using a phone is not repairing one
        ("मैं मोबाइल पर वीडियो देखता हूँ", False),
        ("I fix bikes | I own a mobile phone", False),  # the two words are in different answers
        ("I fix bikes and my mobile phone | I like cooking", True),
    ],
)
def test_pair_keywords_need_both_words_in_the_same_answer(text, expected):
    assert supported("mobile_repair", text) is expected
