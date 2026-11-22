"""Connect: adult learners with similar goals introduce themselves, then talk outside KHOJ."""
from __future__ import annotations

import asyncio
import uuid

import pytest

from app.config import Settings
from tests.conftest import bearer
from tests.test_assignments import API, PHONES, make_student


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        demo_mode=True,
        demo_phones="*",
        jwt_secret="test-secret-0123456789-0123456789-xyz",
        otp_per_ip_per_10min=1000,
        otp_per_phone_per_10min=1000,
    )


async def person(client, clock, db, phone, name, career="tailoring_enterprise", skills=("sewing",), age=20, interests=("secret hobby",)):
    s, _ = await make_student(client, clock, db, phone, career, name)
    uid = s["user"]["id"]
    await db["student_profiles"].update_one({"user_id": uid}, {"$set": {"age": age, "age_band": "18+" if age >= 18 else "16-18", "block": "Haveli", "district": "pune"}})
    await db["intake_sessions"].insert_one({"_id": uuid.uuid4().hex, "user_id": uid, "status": "done", "completed_at": clock.now, "extracted": {"skills": list(skills), "interests": list(interests)}})
    return s


async def view(client, s):
    r = await client.get(f"{API}/connect", headers=bearer(s))
    assert r.status_code == 200, r.text
    return r.json()


async def card_on(client, s, reach="98765 43210", kind="phone", agreed=True, visible=True):
    return await client.put(f"{API}/connect/me", headers=bearer(s), json={"visible": visible, "reach_kind": kind, "reach": reach, "agreed": agreed})


def reach_of(phone: str) -> str:
    """A different valid mobile number for each test person."""
    return "98765" + phone[-5:]


async def ready(client, clock, db, phone, name, **kw):
    s = await person(client, clock, db, phone, name, **kw)
    assert (await card_on(client, s, reach=reach_of(phone))).status_code == 200
    return s


async def card_id_of(client, viewer, name):
    return next(c["card_id"] for c in (await view(client, viewer))["suggestions"] if c["first_name"] == name)


async def ask(client, s, cid):
    return await client.post(f"{API}/connect/{cid}/request", headers=bearer(s))


# ---------------------------------------------------------------------------
# Adults only
# ---------------------------------------------------------------------------


async def test_a_learner_under_18_gets_nothing(client, clock, db):
    kid = await person(client, clock, db, PHONES[0], "Kiran", age=17)
    assert (await view(client, kid)) == {"eligible": False, "opens_at": 18}
    r = await card_on(client, kid)
    assert r.status_code == 403 and r.json()["code"] == "peer_underage"
    for path in ("/connect/abc/request", "/connect/abc/block"):
        assert (await client.post(f"{API}{path}", headers=bearer(kid))).status_code == 403
    assert (await client.post(f"{API}/connect/requests/abc/accept", headers=bearer(kid))).status_code == 403


async def test_a_card_is_never_shown_for_someone_who_is_under_18(client, clock, db):
    me = await ready(client, clock, db, PHONES[0], "Anita")
    other = await ready(client, clock, db, PHONES[1], "Bhavna")
    await db["student_profiles"].update_one({"user_id": other["user"]["id"]}, {"$set": {"age": 16}})  # a record that is no longer adult
    assert (await view(client, me))["suggestions"] == []


async def test_only_students_can_use_it(client, clock, db):
    from tests.test_assignments import make_teacher

    t, _ = await make_teacher(client, clock, db, PHONES[0])
    assert (await client.get(f"{API}/connect", headers=bearer(t))).status_code == 403


# ---------------------------------------------------------------------------
# My card
# ---------------------------------------------------------------------------


async def test_the_card_is_off_until_switched_on(client, clock, db):
    a = await person(client, clock, db, PHONES[0], "Anita")
    v = await view(client, a)
    assert v["eligible"] and v["me"] == {"visible": False, "reach_kind": "phone", "reach": ""} and v["suggestions"] == []


async def test_switching_on_needs_the_tick_and_a_valid_contact(client, clock, db):
    a = await person(client, clock, db, PHONES[0], "Anita")
    r = await card_on(client, a, agreed=False)
    assert r.status_code == 409 and r.json()["code"] == "peer_agree_needed"
    for kind, reach in (("phone", "12345"), ("link", "http://insecure.example/x"), ("phone", "")):
        r = await card_on(client, a, reach=reach, kind=kind)
        assert r.status_code == 422 and r.json()["code"] == "contact_invalid", (kind, reach)
    r = await card_on(client, a, reach="+91 98765-43210")
    assert r.status_code == 200 and r.json()["me"] == {"visible": True, "reach_kind": "phone", "reach": "9876543210"}


async def test_a_card_can_be_switched_off_again(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    b = await ready(client, clock, db, PHONES[1], "Bhavna")
    assert len((await view(client, b))["suggestions"]) == 1
    assert (await card_on(client, a, visible=False)).json()["me"]["visible"] is False
    assert (await view(client, b))["suggestions"] == []


# ---------------------------------------------------------------------------
# What a card shows, and who is suggested
# ---------------------------------------------------------------------------


async def test_a_card_shows_only_the_safe_fields(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita Patil", skills=("sewing", "embroidery"))
    b = await ready(client, clock, db, PHONES[1], "Bhavna Shinde", skills=("sewing",))
    card = (await view(client, b))["suggestions"][0]
    assert card["first_name"] == "Anita" and card["state"] == "Maharashtra" and card["career_id"] == "tailoring_enterprise" and card["same_path"] is True
    assert {s["id"] for s in card["skills"]} == {"sewing", "embroidery"} and card["shared_skills"] == ["sewing"]
    text = str(await view(client, b))
    for secret in ("Patil", reach_of(PHONES[0]), "secret hobby", "Haveli", "pune", a["user"]["id"], "district", "block"):
        assert secret not in text, secret


async def test_suggestions_are_people_on_the_same_path_or_with_a_shared_skill(client, clock, db):
    me = await ready(client, clock, db, PHONES[0], "Me", skills=("sewing",))
    await ready(client, clock, db, PHONES[1], "SamePath", skills=("embroidery",))
    await ready(client, clock, db, PHONES[2], "SharedSkill", career="dairy_poultry", skills=("sewing",))
    await ready(client, clock, db, PHONES[3], "Nothing", career="dairy_poultry", skills=("dairy_care",))
    names = [c["first_name"] for c in (await view(client, me))["suggestions"]]
    assert names[0] == "SamePath" and "SharedSkill" in names and "Nothing" not in names  # same path ranks first


async def test_a_learner_without_a_card_sees_no_suggestions(client, clock, db):
    await ready(client, clock, db, PHONES[1], "Bhavna")
    me = await person(client, clock, db, PHONES[0], "Me")
    assert (await view(client, me))["suggestions"] == []


async def test_a_learner_never_sees_their_own_card(client, clock, db):
    me = await ready(client, clock, db, PHONES[0], "Me")
    assert (await view(client, me))["suggestions"] == []


# ---------------------------------------------------------------------------
# Asking and answering
# ---------------------------------------------------------------------------


async def test_a_request_needs_my_own_card_on(client, clock, db):
    await ready(client, clock, db, PHONES[1], "Bhavna")
    me = await person(client, clock, db, PHONES[0], "Me")
    # without a card there is nobody to ask, and a guessed id is refused too
    other = await db["connect_profiles"].find_one({})
    r = await ask(client, me, other["_id"])
    assert r.status_code == 409 and r.json()["code"] == "peer_need_card"


async def test_asking_and_accepting_shares_the_contact_both_ways(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    b = await person(client, clock, db, PHONES[1], "Bhavna")
    assert (await card_on(client, b, reach="https://t.me/bhavna_s", kind="link")).status_code == 200
    r = await ask(client, a, await card_id_of(client, a, "Bhavna"))
    assert r.status_code == 201 and r.json()["status"] == "pending"

    va = await view(client, a)
    assert va["outgoing"][0]["card"]["first_name"] == "Bhavna" and va["connections"] == [] and "reach" not in str(va["outgoing"])
    assert va["suggestions"] == []  # nobody already asked is suggested again
    vb = await view(client, b)
    assert vb["incoming"][0]["card"]["first_name"] == "Anita" and reach_of(PHONES[0]) not in str(vb)  # nothing shared before accepting
    assert (await client.get(f"{API}/notifications", headers=bearer(b))).json()["items"][0]["kind"] == "connect_request"

    rid = vb["incoming"][0]["id"]
    assert (await client.post(f"{API}/connect/requests/{rid}/accept", headers=bearer(b))).json()["status"] == "accepted"
    vb, va = await view(client, b), await view(client, a)
    assert vb["connections"][0]["reach"] == reach_of(PHONES[0]) and vb["connections"][0]["card"]["first_name"] == "Anita"
    assert va["connections"][0]["reach"] == "https://t.me/bhavna_s" and va["connections"][0]["reach_kind"] == "link"
    assert "connect_accepted" in [n["kind"] for n in (await client.get(f"{API}/notifications", headers=bearer(a))).json()["items"]]


async def test_accepting_needs_my_own_card_on(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    b = await ready(client, clock, db, PHONES[1], "Bhavna")
    await ask(client, a, await card_id_of(client, a, "Bhavna"))
    rid = (await view(client, b))["incoming"][0]["id"]
    await card_on(client, b, visible=False)
    r = await client.post(f"{API}/connect/requests/{rid}/accept", headers=bearer(b))
    assert r.status_code == 409 and r.json()["code"] == "peer_need_card"


async def test_a_declined_request_cannot_be_sent_again(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    b = await ready(client, clock, db, PHONES[1], "Bhavna")
    cid = await card_id_of(client, a, "Bhavna")
    await ask(client, a, cid)
    rid = (await view(client, b))["incoming"][0]["id"]
    assert (await client.post(f"{API}/connect/requests/{rid}/decline", headers=bearer(b))).json()["status"] == "declined"
    assert (await client.post(f"{API}/connect/requests/{rid}/accept", headers=bearer(b))).json()["status"] == "declined"  # first answer stands
    r = await ask(client, a, cid)
    assert r.status_code == 409 and r.json()["code"] == "peer_unavailable"
    assert (await view(client, a))["suggestions"] == [] and (await view(client, a))["outgoing"] == []


async def test_asking_twice_is_one_request(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    await ready(client, clock, db, PHONES[1], "Bhavna")
    cid = await card_id_of(client, a, "Bhavna")
    assert (await ask(client, a, cid)).status_code == 201
    r = await ask(client, a, cid)
    assert r.status_code == 409 and r.json()["code"] == "peer_already"
    assert await db["connections"].count_documents({}) == 1


async def test_asking_someone_who_already_asked_connects_you(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    b = await ready(client, clock, db, PHONES[1], "Bhavna")
    await ask(client, a, await card_id_of(client, a, "Bhavna"))
    cid = (await view(client, b))["incoming"][0]["card"]["card_id"]  # Anita is waiting on Bhavna, so she is not in the suggestions
    r = await ask(client, b, cid)
    assert r.status_code in (200, 201) and r.json()["status"] == "accepted"
    assert len((await view(client, a))["connections"]) == 1


async def test_the_person_who_asked_can_take_it_back_but_not_re_send(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    b = await ready(client, clock, db, PHONES[1], "Bhavna")
    cid = await card_id_of(client, a, "Bhavna")
    await ask(client, a, cid)
    rid = (await view(client, a))["outgoing"][0]["id"]
    assert (await client.post(f"{API}/connect/requests/{rid}/cancel", headers=bearer(a))).json()["status"] == "cancelled"
    assert (await view(client, b))["incoming"] == []
    assert (await ask(client, a, cid)).status_code == 409


async def test_only_five_requests_a_day(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    for i in range(1, 8):
        await ready(client, clock, db, PHONES[i], f"P{i}")
    sent = []
    for c in (await view(client, a))["suggestions"]:
        sent.append((await ask(client, a, c["card_id"])).status_code)
    assert sent == [201] * 5 + [429] * 2
    assert (await view(client, a))["requests_left"] == 0
    clock.advance(60 * 60 * 25)
    from tests.conftest import sign_in

    a = await sign_in(client, clock, PHONES[0])
    assert (await view(client, a))["requests_left"] == 5


async def test_two_people_cannot_answer_for_each_other(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    b = await ready(client, clock, db, PHONES[1], "Bhavna")
    c = await ready(client, clock, db, PHONES[2], "Chitra")
    await ask(client, a, await card_id_of(client, a, "Bhavna"))
    rid = (await view(client, b))["incoming"][0]["id"]
    assert (await client.post(f"{API}/connect/requests/{rid}/accept", headers=bearer(c))).status_code == 404  # not hers to answer
    assert (await client.post(f"{API}/connect/requests/{rid}/accept", headers=bearer(a))).status_code == 404  # the asker cannot accept their own
    assert (await client.post(f"{API}/connect/requests/{rid}/cancel", headers=bearer(c))).status_code == 404


async def test_removing_a_connection_ends_it_for_both(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    b = await ready(client, clock, db, PHONES[1], "Bhavna")
    await ask(client, a, await card_id_of(client, a, "Bhavna"))
    await client.post(f"{API}/connect/requests/{(await view(client, b))['incoming'][0]['id']}/accept", headers=bearer(b))
    conn = (await view(client, a))["connections"][0]["id"]
    assert (await client.post(f"{API}/connect/connections/{conn}/remove", headers=bearer(a))).json()["status"] == "removed"
    assert (await view(client, a))["connections"] == [] and (await view(client, b))["connections"] == []
    assert (await client.post(f"{API}/connect/connections/{conn}/remove", headers=bearer(a))).json()["status"] == "removed"  # twice is one remove


async def test_the_contact_goes_away_when_the_other_person_switches_their_card_off(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    b = await ready(client, clock, db, PHONES[1], "Bhavna")
    await ask(client, a, await card_id_of(client, a, "Bhavna"))
    await client.post(f"{API}/connect/requests/{(await view(client, b))['incoming'][0]['id']}/accept", headers=bearer(b))
    await card_on(client, b, visible=False)
    c = (await view(client, a))["connections"][0]
    assert c["reach"] is None and c["reach_kind"] is None


# ---------------------------------------------------------------------------
# Blocking and reporting
# ---------------------------------------------------------------------------


async def test_a_block_hides_both_people_from_each_other_and_ends_any_connection(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    b = await ready(client, clock, db, PHONES[1], "Bhavna")
    cid = await card_id_of(client, a, "Bhavna")
    await ask(client, a, cid)
    await client.post(f"{API}/connect/requests/{(await view(client, b))['incoming'][0]['id']}/accept", headers=bearer(b))
    assert (await client.post(f"{API}/connect/{cid}/block", headers=bearer(a))).json() == {"blocked": True}
    va, vb = await view(client, a), await view(client, b)
    assert va["connections"] == [] and va["suggestions"] == [] and vb["connections"] == [] and vb["suggestions"] == []
    r = await ask(client, b, (await db["connect_profiles"].find_one({"user_id": a["user"]["id"]}))["_id"])
    assert r.status_code == 404 and r.json()["code"] == "peer_not_found"  # a block is never revealed
    assert (await client.post(f"{API}/connect/{cid}/block", headers=bearer(a))).status_code == 200  # twice is fine


async def test_a_report_also_blocks_and_is_recorded(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    await ready(client, clock, db, PHONES[1], "Bhavna")
    cid = await card_id_of(client, a, "Bhavna")
    r = await client.post(f"{API}/connect/{cid}/report", headers=bearer(a), json={"reason": "pressure"})
    assert r.status_code == 200 and r.json() == {"blocked": True, "reported": True}
    assert (await view(client, a))["suggestions"] == []
    rep = await db["peer_reports"].find_one({})
    assert rep["reason"] == "pressure" and rep["by"] == a["user"]["id"]
    bad = await client.post(f"{API}/connect/{cid}/report", headers=bearer(a), json={"reason": "free text here"})
    assert bad.status_code == 422


async def test_an_unknown_card_id_is_not_found(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    for path in ("request", "block"):
        r = await client.post(f"{API}/connect/nope/{path}", headers=bearer(a))
        assert r.status_code == 404 and r.json()["code"] == "peer_not_found"


async def test_two_people_asking_each_other_at_once_make_one_connection(client, clock, db):
    a = await ready(client, clock, db, PHONES[0], "Anita")
    b = await ready(client, clock, db, PHONES[1], "Bhavna")
    ca = (await db["connect_profiles"].find_one({"user_id": a["user"]["id"]}))["_id"]
    cb = (await db["connect_profiles"].find_one({"user_id": b["user"]["id"]}))["_id"]
    await asyncio.gather(ask(client, a, cb), ask(client, b, ca))
    assert await db["connections"].count_documents({}) == 1


async def test_a_learner_with_no_path_is_told_to_pick_one(client, clock, db):
    from tests.conftest import sign_in

    s = await sign_in(client, clock, PHONES[0])
    r = await client.post(f"{API}/students/profile", headers=bearer(s), json={"name": "Asha", "age": 20, "grade": 12, "district": "pune", "block": "Haveli", "guardian_consent": False})
    assert r.status_code == 201, r.text
    r = await client.get(f"{API}/connect", headers=bearer(s))
    assert r.status_code == 409 and r.json()["code"] == "no_path"
