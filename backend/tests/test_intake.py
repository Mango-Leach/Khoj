"""Voice intake: catalog, answers, translation, extraction, fallbacks and privacy. No network."""
from __future__ import annotations

import json

import pytest

from app import deps
from app.config import Settings
from app.deps import get_llm
from app.main import app
from app.services import catalog
from app.services.cache import MemoryCache
from app.services.llm import LLMRequest, LLMService, ProviderError, Task, route_for
from app.services.privacy import scrub_text
from tests.conftest import OTHER_PHONE, STUDENT, TEACHER, bearer, sign_in

API = "/api/v1"


@pytest.fixture(autouse=True)
def _fresh_llm_singleton():
    deps._llm_service = None
    yield
    deps._llm_service = None


class Scripted:
    """A provider whose answers come from a function, and which remembers what it was asked."""

    def __init__(self, name: str, handler) -> None:
        self.name = name
        self.handler = handler
        self.seen: list[tuple[Task, str]] = []

    def model_for(self, req: LLMRequest) -> str:
        return f"{self.name}-model"

    async def complete(self, req: LLMRequest) -> str:
        self.seen.append((req.task, req.prompt))
        return self.handler(req)


EXTRACTION_OK = json.dumps(
    {"skills": ["sewing", "sewing_machine_care"], "other_skills": [], "interests": ["stitching clothes"], "goal": "Run my own tailoring shop"}
)


@pytest.fixture
def llm(client):
    """A live LLM service over two scripted providers, wired in place of the real one."""
    translations = {"मी शिलाई मशीन दुरुस्त करते": "I repair sewing machines"}

    def gemini(req: LLMRequest) -> str:
        if req.task is Task.TRANSLATION:
            text = req.prompt.split("Text: ", 1)[1]
            return json.dumps({"english": translations.get(text, text)})
        return EXTRACTION_OK

    def ollama(req: LLMRequest) -> str:
        return EXTRACTION_OK

    settings = Settings(_env_file=None, llm_mode="live", jwt_secret="x" * 40)
    providers = {"ollama": Scripted("ollama", ollama), "gemini": Scripted("gemini", gemini)}
    service = LLMService(settings, providers, MemoryCache())
    app.dependency_overrides[get_llm] = lambda: service
    return service


# --- helpers -----------------------------------------------------------------


async def student(client, clock, phone="9876543210"):
    tokens = await sign_in(client, clock, phone)
    r = await client.post(f"{API}/students/profile", json=STUDENT, headers=bearer(tokens))
    assert r.status_code == 201, r.text
    return tokens


OPEN = {
    "q_enjoy": "I like stitching clothes",
    "q_skill": "I repair the sewing machine at home",
}
CHOICES = {"q_work": "work_earned", "q_hours": "hours_5_10", "q_move": "move_no", "q_budget": "budget_low", "q_goal": "goal_earn_soon"}


async def start(client, tokens, **body):
    r = await client.post(f"{API}/intake/sessions", json={"category_ids": ["textile"], **body}, headers=bearer(tokens))
    assert r.status_code == 201, r.text
    return r.json()


async def answer(client, tokens, sid, qid, **fields):
    return await client.post(f"{API}/intake/sessions/{sid}/confirm", json={"question_id": qid, **fields}, headers=bearer(tokens))


async def fill(client, tokens, sid, language="en", open_answers=None):
    for qid, text in (open_answers or OPEN).items():
        r = await answer(client, tokens, sid, qid, transcript=text, language=language, source="typed")
        assert r.status_code == 200, r.text
    for qid, cid in CHOICES.items():
        r = await answer(client, tokens, sid, qid, choice_id=cid, language=language, source="tap")
        assert r.status_code == 200, r.text


# --- catalog and data integrity ----------------------------------------------


async def test_catalog_endpoints_are_public_and_complete(client):
    cats = (await client.get(f"{API}/catalog/categories")).json()["categories"]
    assert len(cats) == 8 and all(set(c["name"]) == {"en", "hi", "mr"} for c in cats)
    skills = (await client.get(f"{API}/catalog/skills")).json()["skills"]
    assert len(skills) >= 30
    assert all("keywords" not in s for s in skills)  # matching keywords stay on the server


def test_every_skill_question_and_choice_has_all_three_languages():
    families = {c["id"] for c in catalog.categories()} | {"general"}
    for s in catalog.skills():
        assert set(s["name"]) == {"en", "hi", "mr"} and all(s["name"].values()), s["id"]
        assert s["family"] in families, s["id"]
        assert s["keywords"], s["id"]
    for q in catalog.questions():
        assert set(q["text"]) == {"en", "hi", "mr"} and all(q["text"].values()), q["id"]
        for c in q.get("choices", []):
            assert set(c["label"]) == {"en", "hi", "mr"} and all(c["label"].values()), c["id"]
    assert len(catalog.questions()) == 7
    open_questions = [q for q in catalog.questions() if q["kind"] == "open"]
    assert [q["id"] for q in open_questions] == ["q_enjoy", "q_skill"]  # only these are read for skills
    for q in open_questions:  # each open question shows an example answer, so people know how much to say
        assert set(q["example"]) == {"en", "hi", "mr"} and all(q["example"].values()), q["id"]


def test_choice_effects_only_set_known_constraint_values():
    allowed = {
        "budget": {"none", "low", "medium"},
        "can_move_away": {"yes", "no", "unknown"},
        "earned_before": {"earned", "helped", "no"},
        "priority": {"earn_soon", "earn_more", "near_home", "govt_job", "own_business"},
    }
    for q in catalog.questions():
        for c in q.get("choices", []):
            for key, value in c["effect"].items():
                if key == "hours_per_week":
                    assert isinstance(value, int) and 0 <= value <= 80
                else:
                    assert value in allowed[key], (q["id"], c["id"])


def test_translation_defaults_to_gemini_and_extraction_stays_local_first():
    s = Settings(_env_file=None)
    assert route_for(s, Task.TRANSLATION) == "gemini"
    assert route_for(s, Task.EXTRACTION) == "ollama"


# --- privacy -----------------------------------------------------------------


def test_scrub_removes_phone_numbers_emails_and_links_but_keeps_ordinary_numbers():
    out = scrub_text("call 98765 43210 or +91-9876543210, mail a.b@x.com, see https://x.y/z. I am in class 10 and study 12 hours")
    assert "98765" not in out and "@" not in out and "http" not in out
    assert "class 10" in out and "12 hours" in out


def test_scrub_handles_devanagari_digits():
    assert "९८७६" not in scrub_text("मेरा नंबर ९८७६५४३२१० है")


# --- access ------------------------------------------------------------------


async def test_intake_is_for_students_only(client, clock):
    assert (await client.get(f"{API}/intake/questions")).status_code == 401
    t = await sign_in(client, clock)
    assert (await client.post(f"{API}/teachers/profile", json=TEACHER, headers=bearer(t))).status_code == 201
    r = await client.post(f"{API}/intake/sessions", json={}, headers=bearer(t))
    assert r.status_code == 403 and r.json()["code"] == "wrong_role"


async def test_a_session_belongs_to_its_owner(client, clock, llm):
    a = await student(client, clock)
    sid = (await start(client, a))["id"]
    b = await sign_in(client, clock, OTHER_PHONE)
    assert (await client.post(f"{API}/students/profile", json={**STUDENT, "name": "Other"}, headers=bearer(b))).status_code == 201
    for call in (
        client.get(f"{API}/intake/sessions/{sid}", headers=bearer(b)),
        answer(client, b, sid, "q_enjoy", transcript="hello"),
    ):
        r = await call
        assert r.status_code == 404 and r.json()["code"] == "session_not_found"


# --- sessions ----------------------------------------------------------------


async def test_session_validation_and_one_live_session_at_a_time(client, clock, llm):
    t = await student(client, clock)
    r = await client.post(f"{API}/intake/sessions", json={"category_ids": ["nope"]}, headers=bearer(t))
    assert r.status_code == 422 and r.json()["code"] == "unknown_category"
    r = await client.post(f"{API}/intake/sessions", json={"category_ids": ["textile", "food", "care", "trades"]}, headers=bearer(t))
    assert r.status_code == 422

    first = await start(client, t)
    second = await start(client, t, not_sure=True)
    assert second["category_ids"] == [] and second["not_sure"] is True  # "not sure" drops any tiles
    assert (await client.get(f"{API}/intake/sessions/latest", headers=bearer(t))).json()["id"] == second["id"]
    assert (await client.get(f"{API}/intake/sessions/{first['id']}", headers=bearer(t))).json()["status"] == "abandoned"


async def test_next_walks_the_seven_questions(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    n = (await client.get(f"{API}/intake/sessions/{sid}/next", headers=bearer(t))).json()
    assert n["question"]["id"] == "q_enjoy" and n["number"] == 1 and n["total"] == 7 and n["done"] is False
    await answer(client, t, sid, "q_enjoy", transcript="I like stitching")
    n = (await client.get(f"{API}/intake/sessions/{sid}/next", headers=bearer(t))).json()
    assert n["question"]["id"] == "q_skill" and n["number"] == 2


# --- answers -----------------------------------------------------------------


async def test_english_answers_are_stored_scrubbed_and_untranslated(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    r = await answer(client, t, sid, "q_enjoy", transcript="I like sewing, call me on 98765 43210", language="en")
    a = r.json()["answers"][0]
    assert "98765" not in a["transcript"] and a["translation"] == "not_needed"
    assert llm.providers["gemini"].seen == []  # nothing to translate, so no provider call


MARATHI = "मी शिलाई मशीन दुरुस्त करते"


async def test_confirming_a_marathi_answer_saves_it_without_waiting_on_any_provider(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    r = await answer(client, t, sid, "q_skill", transcript=MARATHI, language="mr", source="browser_asr")
    a = r.json()["answers"][0]
    assert a["transcript"] == MARATHI and a["translation"] == "pending" and a["transcript_en"] == "" and a["source"] == "browser_asr"
    assert llm.providers["gemini"].seen == [] and llm.providers["ollama"].seen == []  # the tap is instant


async def test_pending_answers_are_translated_by_gemini_when_the_intake_completes(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    await fill(client, t, sid, language="mr", open_answers={**OPEN, "q_skill": MARATHI})
    view = (await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))).json()
    by_q = {a["question_id"]: a for a in view["answers"]}
    assert by_q["q_skill"]["transcript_en"] == "I repair sewing machines" and by_q["q_skill"]["translation"] == "ok"
    assert all(a["translation"] in ("ok", "not_needed") for a in view["answers"])  # nothing is left pending
    translated = [task for task, _ in llm.providers["gemini"].seen if task is Task.TRANSLATION]
    assert len(translated) == 2  # the two open answers, one call each
    assert llm.providers["ollama"].seen and all(task is Task.EXTRACTION for task, _ in llm.providers["ollama"].seen)


async def test_a_failed_translation_keeps_the_original_and_says_so(client, clock, llm):
    def boom(req):
        if req.task is Task.TRANSLATION:
            raise ProviderError("down")
        return EXTRACTION_OK

    llm.providers["gemini"].handler = boom
    llm.providers["ollama"].handler = boom
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    await fill(client, t, sid, language="mr", open_answers={**OPEN, "q_skill": MARATHI})
    view = (await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))).json()
    a = next(x for x in view["answers"] if x["question_id"] == "q_skill")
    assert a["translation"] == "failed" and a["transcript_en"] == a["transcript"]
    assert view["status"] == "review"  # a dead translator never blocks the learner


async def test_choice_questions_need_a_tapped_choice(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    r = await answer(client, t, sid, "q_hours", transcript="five hours")
    assert r.status_code == 422 and r.json()["code"] == "choice_required"
    r = await answer(client, t, sid, "q_hours", choice_id="hours_5_10", language="hi", source="tap")
    a = r.json()["answers"][0]
    assert a["choice_id"] == "hours_5_10" and a["transcript"] == "5 से 10 घंटे" and a["transcript_en"] == "5 to 10 hours"


async def test_answer_validation(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    assert (await answer(client, t, sid, "q_nope", transcript="x")).json()["code"] == "unknown_question"
    assert (await answer(client, t, sid, "q_enjoy", transcript=" ")).json()["code"] == "empty_answer"
    assert (await answer(client, t, sid, "q_enjoy", transcript="hello", choice_id="hours_5_10")).json()["code"] == "unexpected_choice"


async def test_answering_again_replaces_the_earlier_answer(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    await answer(client, t, sid, "q_enjoy", transcript="first try")
    r = await answer(client, t, sid, "q_enjoy", transcript="second try")
    answers = r.json()["answers"]
    assert len(answers) == 1 and answers[0]["transcript"] == "second try"


# --- extraction --------------------------------------------------------------


async def test_complete_needs_enough_answers(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    await answer(client, t, sid, "q_enjoy", transcript="I like sewing")
    r = await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))
    assert r.status_code == 409 and r.json()["code"] == "not_enough_answers"


async def test_extraction_uses_the_local_model_first_and_checks_the_output(client, clock, llm):
    llm.providers["ollama"].handler = lambda req: json.dumps(
        {"skills": ["Sewing", "sewing machine care", "plumbing wizard", "sewing"], "other_skills": ["pattern drafting"], "interests": ["stitching"], "goal": "my own shop"}
    )
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    await fill(client, t, sid)
    r = await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))
    assert r.status_code == 200, r.text
    view = r.json()
    ex = view["extracted"]
    assert view["status"] == "review" and view["extraction_source"] == "ollama"
    assert ex["skills"] == ["sewing", "sewing_machine_care"]  # ids from the vocabulary, de-duplicated
    assert "plumbing wizard" in ex["other_skills"] and "pattern drafting" in ex["other_skills"]  # unknown ones become free text
    # constraints come from the taps, not from the model
    assert ex["constraints"] == {"budget": "low", "can_move_away": "no", "hours_per_week": 7, "earned_before": "earned", "priority": "earn_soon"}


async def test_invalid_output_from_the_primary_fails_over_to_the_other_provider(client, clock, llm):
    llm.providers["ollama"].handler = lambda req: "this is not json"
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    await fill(client, t, sid)
    view = (await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))).json()
    assert view["extraction_source"] == "gemini" and "sewing" in view["extracted"]["skills"]


async def test_extraction_falls_back_to_keywords_when_no_provider_answers(client, clock, llm):
    def boom(req):
        raise ProviderError("down")

    llm.providers["ollama"].handler = boom
    llm.providers["gemini"].handler = boom
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    await fill(client, t, sid)
    view = (await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))).json()
    assert view["extraction_source"] == "fallback"
    assert {"sewing", "sewing_machine_care", "repair_general"} <= set(view["extracted"]["skills"])
    assert view["extracted"]["constraints"]["hours_per_week"] == 7  # still deterministic


async def test_keyword_fallback_understands_marathi(client, clock, llm):
    def boom(req):
        raise ProviderError("down")

    llm.providers["ollama"].handler = boom
    llm.providers["gemini"].handler = boom
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    marathi = {
        "q_enjoy": "मला शिवणकाम आवडतं",
        "q_skill": "मी घरी शिलाई मशीन दुरुस्त करते आणि शेजाऱ्यांसाठी कपडे शिवते",
    }
    await fill(client, t, sid, language="mr", open_answers=marathi)
    view = (await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))).json()
    assert {"sewing", "sewing_machine_care"} <= set(view["extracted"]["skills"])


async def test_no_personal_data_reaches_any_provider(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    spoken = {**OPEN, "q_skill": "I stitch blouses. My number is 98765 43210"}
    await fill(client, t, sid, open_answers=spoken)
    await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))
    prompts = " ".join(p for provider in llm.providers.values() for _, p in provider.seen)
    assert "98765" not in prompts
    assert "Haveli" not in prompts and "pune" not in prompts.lower()  # no location from the profile
    assert "age band: 16-18" in prompts.lower()  # an age band, never the age or the name


async def test_cache_only_mode_never_calls_a_provider_and_still_extracts(client, clock):
    t = await student(client, clock)  # no llm fixture: the real service in cache_only mode
    sid = (await start(client, t))["id"]
    await fill(client, t, sid)
    view = (await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))).json()
    assert view["extraction_source"] == "fallback" and "sewing" in view["extracted"]["skills"]


# --- review and accept -------------------------------------------------------


async def test_accept_lets_the_learner_remove_add_from_the_list_but_not_invent_free_text(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    await fill(client, t, sid)
    await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))
    r = await client.post(
        f"{API}/intake/sessions/{sid}/accept",
        json={"skills": ["sewing", "plumbing", "made_up_skill"], "other_skills": ["made up skill"], "interests": ["stitching clothes", "invented"], "goal": "Run my own tailoring shop"},
        headers=bearer(t),
    )
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["status"] == "done"
    ex = view["extracted"]
    assert ex["skills"] == ["sewing", "plumbing"]  # sewing_machine_care removed; plumbing added by the learner from the list
    assert ex["learner_added"] == ["plumbing"]  # and remembered as theirs, not read from their words
    assert "made_up_skill" not in ex["skills"] and ex["other_skills"] == []  # an id that is not on the list is dropped
    assert ex["interests"] == ["stitching clothes"]  # free text still cannot be invented
    assert (await client.get(f"{API}/intake/sessions/latest", headers=bearer(t))).json()["status"] == "done"
    # a finished intake is closed
    assert (await answer(client, t, sid, "q_enjoy", transcript="more")).json()["code"] == "session_closed"


async def test_a_learner_can_rescue_an_empty_result_by_adding_their_own_skills(client, clock, llm):
    llm.providers["ollama"].handler = lambda req: json.dumps({"skills": [], "other_skills": [], "interests": [], "goal": None})
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    await fill(client, t, sid, open_answers={"q_enjoy": "I like quiet time", "q_skill": "I help at home"})
    view = (await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))).json()
    assert view["extracted"]["skills"] == []
    r = await client.post(f"{API}/intake/sessions/{sid}/accept", json={"skills": ["cooking", "baking"]}, headers=bearer(t))
    assert r.status_code == 200 and r.json()["extracted"]["skills"] == ["cooking", "baking"]
    assert r.json()["extracted"]["learner_added"] == ["cooking", "baking"]


async def test_at_most_eight_skills_and_extracted_ones_are_not_marked_as_added(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    await fill(client, t, sid)
    await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))
    nine = ["sewing", "embroidery", "cooking", "baking", "catering", "plumbing", "solar_basics", "photography", "tutoring"]
    assert (await client.post(f"{API}/intake/sessions/{sid}/accept", json={"skills": nine}, headers=bearer(t))).status_code == 422
    eight = nine[:8]
    ex = (await client.post(f"{API}/intake/sessions/{sid}/accept", json={"skills": eight}, headers=bearer(t))).json()["extracted"]
    assert ex["skills"] == eight and "sewing" not in ex["learner_added"]  # sewing was read from their words
    assert ex["learner_added"] == eight[1:]


async def test_accept_before_extraction_is_refused(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    r = await client.post(f"{API}/intake/sessions/{sid}/accept", json={}, headers=bearer(t))
    assert r.status_code == 409 and r.json()["code"] == "nothing_to_accept"


# --- evidence: the learner's words decide, never the tiles --------------------


async def test_ticked_tiles_are_interest_not_evidence(client, clock, llm):
    """The reported bug: tiles for art, care and trades produced photography and tutoring for someone who said 'painting'."""
    llm.providers["ollama"].handler = lambda req: json.dumps({"skills": ["photography", "tutoring", "handicraft"], "other_skills": [], "interests": [], "goal": None})
    t = await student(client, clock)
    sid = (await start(client, t, category_ids=["creative", "care", "trades"]))["id"]
    await fill(client, t, sid, open_answers={"q_enjoy": "painting", "q_skill": "painting"})
    view = (await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))).json()
    assert view["extraction_source"] == "ollama"
    assert view["extracted"]["skills"] == ["handicraft"]  # photography and tutoring have no support in "painting"


async def test_the_tiles_never_reach_the_prompt(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t, category_ids=["creative", "care", "trades"]))["id"]
    await fill(client, t, sid)
    await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))
    prompts = " ".join(p for provider in llm.providers.values() for task, p in provider.seen if task is Task.EXTRACTION)
    assert "Areas the learner" not in prompts
    assert "Art, photos and videos" not in prompts and "Care and teaching" not in prompts and "Repair and trades" not in prompts


async def test_a_hosted_model_is_held_to_the_same_rule(client, clock, llm):
    llm.providers["ollama"].handler = lambda req: "not json"
    llm.providers["gemini"].handler = lambda req: json.dumps({"skills": ["sewing", "plumbing", "baking"], "other_skills": [], "interests": [], "goal": None}) if req.task is Task.EXTRACTION else json.dumps({"english": "x"})
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    await fill(client, t, sid)
    view = (await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))).json()
    assert view["extraction_source"] == "gemini" and view["extracted"]["skills"] == ["sewing"]


async def test_tapped_answers_are_not_read_as_skills(client, clock, llm):
    """'work_earned' and 'goal_business' mention earning and business; only the two open answers count."""
    llm.providers["ollama"].handler = lambda req: json.dumps({"skills": ["shop_keeping"], "other_skills": [], "interests": [], "goal": None})
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    await fill(client, t, sid, open_answers={"q_enjoy": "I like watching cricket", "q_skill": "I play with my friends"})
    view = (await client.post(f"{API}/intake/sessions/{sid}/complete", headers=bearer(t))).json()
    assert view["extracted"]["skills"] == []


async def test_work_and_goal_are_tap_only(client, clock, llm):
    t = await student(client, clock)
    sid = (await start(client, t))["id"]
    for qid in ("q_work", "q_goal"):
        r = await answer(client, t, sid, qid, transcript="in words")
        assert r.status_code == 422 and r.json()["code"] == "choice_required"
