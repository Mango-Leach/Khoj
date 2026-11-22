"""A day in the life: a mentor offers 30 or 45 minute calls, a learner on that path books one."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.services import calls
from tests.conftest import bearer, sign_in
from tests.test_assignments import API, PHONES, make_student, make_teacher

LINK = "https://meet.google.com/abc-defg-hij"


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


def at(clock, days=1, hour=11, minute=0) -> datetime:
    """A time in Indian time, `days` ahead of the test clock."""
    local = (clock.now + timedelta(days=days)).astimezone(calls.IST)
    return local.replace(hour=hour, minute=minute, second=0, microsecond=0)


def body(clock, **over) -> dict:
    b = {"career_id": "tailoring_enterprise", "starts_at": at(clock).isoformat(), "minutes": 30, "contact_kind": "link", "contact": LINK}
    b.update(over)
    if isinstance(b["starts_at"], datetime):
        b["starts_at"] = b["starts_at"].isoformat()
    return b


async def host(client, clock, db, phone, areas=("tailoring",), on=True):
    t, tid = await make_teacher(client, clock, db, phone, areas)
    if on:
        r = await client.patch(f"{API}/teachers/me/calls", headers=bearer(t), json={"offers_calls": True})
        assert r.status_code == 200, r.text
    return t, tid


async def add(client, t, payload):
    return await client.post(f"{API}/teachers/me/calls/slots", headers=bearer(t), json=payload)


async def learner(client, clock, db, phone, career="tailoring_enterprise", name="Priya", adult=False):
    s, jid = await make_student(client, clock, db, phone, career, name)
    if adult:
        await db["student_profiles"].update_one({"user_id": s["user"]["id"]}, {"$set": {"age": 20, "age_band": "18+"}})
    return s, jid


async def open_slots(client, s):
    r = await client.get(f"{API}/calls", headers=bearer(s))
    assert r.status_code == 200, r.text
    return r.json()


async def book(client, s, slot_id, **over):
    return await client.post(f"{API}/calls/{slot_id}/book", headers=bearer(s), json={"agreed": True, "guardian_near": True, **over})


async def notes(client, tokens):
    r = await client.get(f"{API}/notifications", headers=bearer(tokens))
    return [n["kind"] for n in r.json()["items"]]


# ---------------------------------------------------------------------------
# Who may host
# ---------------------------------------------------------------------------


async def test_a_mentor_who_is_not_verified_cannot_switch_calls_on(client, clock, db):
    t = await sign_in(client, clock, PHONES[0])
    r = await client.post(f"{API}/teachers/profile", headers=bearer(t), json={"name": "Sunita", "roles": ["teacher"], "languages": ["mr"], "district": "pune", "block": "Haveli", "weekly_hours": 6})
    assert r.status_code == 201
    r = await client.patch(f"{API}/teachers/me/calls", headers=bearer(t), json={"offers_calls": True})
    assert r.status_code == 409 and r.json()["code"] == "not_verified"
    view = (await client.get(f"{API}/teachers/me/calls", headers=bearer(t))).json()
    assert view["offers_calls"] is False and view["can_host"] is False and view["careers"] == []


async def test_a_verified_mentor_can_host_only_careers_their_skill_covers(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    view = (await client.get(f"{API}/teachers/me/calls", headers=bearer(t))).json()
    ids = {c["career_id"] for c in view["careers"]}
    assert view["offers_calls"] and "tailoring_enterprise" in ids and "electrician_wiring" not in ids
    r = await add(client, t, body(clock, career_id="electrician_wiring"))
    assert r.status_code == 409 and r.json()["code"] == "not_hostable"


async def test_slots_need_the_switch_on(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0], on=False)
    r = await add(client, t, body(clock))
    assert r.status_code == 409 and r.json()["code"] == "calls_off"


async def test_the_label_names_the_check_that_was_passed_not_a_list_of_skills(client, clock, db):
    """One check proves a bundle of skills, so the label says "Digital marketing for local shops", not each skill in it."""
    t, _ = await host(client, clock, db, PHONES[0], areas=("digital_marketing",))
    view = (await client.get(f"{API}/teachers/me/calls", headers=bearer(t))).json()
    shops = next(c for c in view["careers"] if c["career_id"] == "digital_marketing_shops")
    assert [a["id"] for a in shops["verified_in"]] == ["digital_marketing"]
    assert shops["verified_in"][0]["name"]["en"] == "Digital marketing for local shops"
    slot = (await add(client, t, body(clock, career_id="digital_marketing_shops"))).json()
    s, _ = await learner(client, clock, db, PHONES[1], career="digital_marketing_shops")
    host_card = (await open_slots(client, s))["slots"][0]["host"]
    assert [a["id"] for a in host_card["verified_in"]] == ["digital_marketing"]
    assert slot["career_name"]


# ---------------------------------------------------------------------------
# Posting times
# ---------------------------------------------------------------------------


async def test_a_slot_is_posted_with_its_contact_kept_for_the_host(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    r = await add(client, t, body(clock, minutes=45))
    assert r.status_code == 201, r.text
    slot = r.json()
    assert slot["minutes"] == 45 and slot["status"] == "open" and slot["contact"] == LINK and slot["learner"] is None


@pytest.mark.parametrize(
    "over, code",
    [
        ({"starts_at": "SOON"}, "slot_too_soon"),
        ({"starts_at": "FAR"}, "slot_too_far"),
        ({"starts_at": "NIGHT"}, "slot_hours"),
        ({"starts_at": "LATE"}, "slot_hours"),  # starts before 9 pm but would end after it
        ({"contact": "http://insecure.example/room"}, "contact_invalid"),
        ({"contact_kind": "phone", "contact": "12345"}, "contact_invalid"),
    ],
)
async def test_bad_times_and_contacts_are_refused(client, clock, db, over, code):
    t, _ = await host(client, clock, db, PHONES[0])
    when = {
        "SOON": (clock.now + timedelta(minutes=90)).astimezone(calls.IST).replace(hour=12),  # replaced below
        "FAR": at(clock, days=40),
        "NIGHT": at(clock, hour=5),
        "LATE": at(clock, hour=20, minute=45),
    }
    if over.get("starts_at") == "SOON":
        over = {**over, "starts_at": clock.now + timedelta(minutes=90)}
    elif over.get("starts_at") in when:
        over = {**over, "starts_at": when[over["starts_at"]]}
    r = await add(client, t, body(clock, **over))
    assert r.status_code == 422 and r.json()["code"] == code, r.text


async def test_a_phone_number_is_kept_as_ten_digits(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    r = await add(client, t, body(clock, contact_kind="phone", contact="+91 98765-43210"))
    assert r.status_code == 201 and r.json()["contact"] == "9876543210"


async def test_two_calls_cannot_overlap_and_there_is_a_limit(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    assert (await add(client, t, body(clock, starts_at=at(clock, hour=11)))).status_code == 201
    r = await add(client, t, body(clock, starts_at=at(clock, hour=11, minute=20)))
    assert r.status_code == 409 and r.json()["code"] == "slot_overlaps"
    for n in range(calls.MAX_OPEN_SLOTS - 1):
        assert (await add(client, t, body(clock, starts_at=at(clock, days=2 + n, hour=11)))).status_code == 201
    r = await add(client, t, body(clock, starts_at=at(clock, days=20, hour=11)))
    assert r.status_code == 409 and r.json()["code"] == "too_many_slots"


# ---------------------------------------------------------------------------
# Finding and booking a call
# ---------------------------------------------------------------------------


async def test_a_learner_sees_times_for_their_path_without_any_contact(client, clock, db):
    t, tid = await host(client, clock, db, PHONES[0])
    s, _ = await learner(client, clock, db, PHONES[1])
    assert (await add(client, t, body(clock))).status_code == 201
    view = await open_slots(client, s)
    assert view["career_id"] == "tailoring_enterprise" and view["needs_guardian"] is True and view["can_book"] is True
    (slot,) = view["slots"]
    assert slot["host"]["teacher_id"] == tid and slot["host"]["verified_in"] and slot["host"]["speaks_your_language"] is not None
    text = str(view)
    assert LINK not in text and "contact" not in slot and "teacher_id" in slot["host"]
    assert "user_id" not in str(slot["host"])


async def test_a_learner_needs_no_mentor_to_book(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    s, jid = await learner(client, clock, db, PHONES[1])
    assert (await db["journeys"].find_one({"_id": jid}))["state"] == "path_selected"  # no mentor yet
    slot = (await add(client, t, body(clock))).json()
    r = await book(client, s, slot["id"])
    assert r.status_code == 200, r.text
    assert r.json()["contact"] == LINK and r.json()["host"]["name"]


async def test_a_learner_on_another_path_sees_and_books_nothing(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    other, _ = await learner(client, clock, db, PHONES[1], career="dairy_poultry")
    slot = (await add(client, t, body(clock))).json()
    assert (await open_slots(client, other))["slots"] == []
    r = await book(client, other, slot["id"])
    assert r.status_code == 409 and r.json()["code"] == "call_wrong_path"


async def test_a_learner_with_no_path_is_told_to_pick_one(client, clock, db):
    s = await sign_in(client, clock, PHONES[1])
    await client.post(f"{API}/students/profile", headers=bearer(s), json={"name": "Priya", "age": 20, "grade": 12, "district": "pune", "block": "Haveli", "guardian_consent": False})
    r = await client.get(f"{API}/calls", headers=bearer(s))
    assert r.status_code == 409 and r.json()["code"] == "no_path"


async def test_booking_needs_the_code_of_conduct_and_a_guardian_for_a_minor(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    minor, _ = await learner(client, clock, db, PHONES[1])
    adult, _ = await learner(client, clock, db, PHONES[2], adult=True)
    slot = (await add(client, t, body(clock))).json()
    r = await book(client, minor, slot["id"], agreed=False)
    assert r.status_code == 409 and r.json()["code"] == "call_conduct_needed"
    r = await book(client, minor, slot["id"], guardian_near=False)
    assert r.status_code == 409 and r.json()["code"] == "call_guardian_needed"
    r = await book(client, adult, slot["id"], guardian_near=False)  # an adult does not need one
    assert r.status_code == 200, r.text


async def test_a_slot_goes_to_one_learner_and_a_resend_is_one_booking(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    a, _ = await learner(client, clock, db, PHONES[1])
    b, _ = await learner(client, clock, db, PHONES[2], name="Asha")
    slot = (await add(client, t, body(clock))).json()
    first = await book(client, a, slot["id"])
    again = await book(client, a, slot["id"])
    assert first.status_code == again.status_code == 200 and first.json()["id"] == again.json()["id"]
    r = await book(client, b, slot["id"])
    assert r.status_code == 409 and r.json()["code"] == "call_taken"
    assert (await open_slots(client, b))["slots"] == []  # a booked time is not offered to anyone else


async def test_a_learner_holds_one_call_at_a_time(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    s, _ = await learner(client, clock, db, PHONES[1])
    one = (await add(client, t, body(clock, starts_at=at(clock, hour=11)))).json()
    two = (await add(client, t, body(clock, starts_at=at(clock, days=2, hour=11)))).json()
    assert (await book(client, s, one["id"])).status_code == 200
    view = await open_slots(client, s)
    assert view["can_book"] is False and len(view["upcoming"]) == 1
    r = await book(client, s, two["id"])
    assert r.status_code == 409 and r.json()["code"] == "call_limit"


async def test_the_host_is_told_and_sees_a_first_name_never_a_phone(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    s, _ = await learner(client, clock, db, PHONES[1], name="Priya Patil")
    slot = (await add(client, t, body(clock))).json()
    assert (await book(client, s, slot["id"])).status_code == 200
    assert "call_booked" in await notes(client, t)
    (mine,) = (await client.get(f"{API}/teachers/me/calls", headers=bearer(t))).json()["upcoming"]
    assert mine["status"] == "booked" and mine["learner"]["first_name"] == "Priya" and mine["learner"]["guardian_near"] is True
    assert "Patil" not in str(mine) and "9000" not in str(mine["learner"])


async def test_a_time_too_close_to_start_cannot_be_booked(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    s, _ = await learner(client, clock, db, PHONES[1])
    slot = (await add(client, t, body(clock))).json()
    clock.advance(60 * 60 * 17)  # the call is now less than the booking lead away
    s = await sign_in(client, clock, PHONES[1])
    assert (await open_slots(client, s))["slots"] == []
    r = await book(client, s, slot["id"])
    assert r.status_code == 409 and r.json()["code"] == "call_taken"


# ---------------------------------------------------------------------------
# Cancelling
# ---------------------------------------------------------------------------


async def test_a_learner_can_give_the_time_back_and_it_opens_again(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    a, _ = await learner(client, clock, db, PHONES[1])
    b, _ = await learner(client, clock, db, PHONES[2], name="Asha")
    slot = (await add(client, t, body(clock))).json()
    assert (await book(client, a, slot["id"])).status_code == 200
    r = await client.post(f"{API}/calls/{slot['id']}/cancel", headers=bearer(a))
    assert r.status_code == 200 and r.json()["cancelled"] is True
    assert "call_cancelled" in await notes(client, t)
    assert len((await open_slots(client, b))["slots"]) == 1
    assert (await book(client, b, slot["id"])).status_code == 200
    again = await client.post(f"{API}/calls/{slot['id']}/cancel", headers=bearer(a))  # a is no longer the holder
    assert again.status_code == 404


async def test_a_mentor_cancelling_tells_the_learner(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    s, _ = await learner(client, clock, db, PHONES[1])
    slot = (await add(client, t, body(clock))).json()
    assert (await book(client, s, slot["id"])).status_code == 200
    r = await client.post(f"{API}/teachers/me/calls/slots/{slot['id']}/cancel", headers=bearer(t))
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert "call_cancelled" in await notes(client, s)
    assert (await client.post(f"{API}/teachers/me/calls/slots/{slot['id']}/cancel", headers=bearer(t))).status_code == 200  # twice is one
    assert (await open_slots(client, s))["upcoming"] == []


async def test_switching_calls_off_takes_open_times_down_but_keeps_a_booked_call(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    s, _ = await learner(client, clock, db, PHONES[1])
    booked = (await add(client, t, body(clock, starts_at=at(clock, hour=11)))).json()
    await add(client, t, body(clock, starts_at=at(clock, days=2, hour=11)))
    assert (await book(client, s, booked["id"])).status_code == 200
    r = await client.patch(f"{API}/teachers/me/calls", headers=bearer(t), json={"offers_calls": False})
    assert r.status_code == 200
    view = r.json()
    assert [u["status"] for u in view["upcoming"]] == ["booked"]
    assert (await open_slots(client, s))["slots"] == []


async def test_a_host_who_loses_their_verification_is_no_longer_offered(client, clock, db):
    t, tid = await host(client, clock, db, PHONES[0])
    s, _ = await learner(client, clock, db, PHONES[1])
    await add(client, t, body(clock))
    assert len((await open_slots(client, s))["slots"]) == 1
    await db["teacher_profiles"].update_one({"_id": tid}, {"$set": {"tier": 0}})
    assert (await open_slots(client, s))["slots"] == []


# ---------------------------------------------------------------------------
# After the call
# ---------------------------------------------------------------------------


async def test_the_learner_records_whether_the_call_happened(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    s, _ = await learner(client, clock, db, PHONES[1])
    slot = (await add(client, t, body(clock, minutes=45))).json()
    assert (await book(client, s, slot["id"])).status_code == 200
    r = await client.post(f"{API}/calls/{slot['id']}/feedback", headers=bearer(s), json={"took_place": True, "rating": 5})
    assert r.status_code == 409 and r.json()["code"] == "call_not_ended"
    clock.advance(60 * 60 * 24)
    s, t = await sign_in(client, clock, PHONES[1]), await sign_in(client, clock, PHONES[0])
    r = await client.post(f"{API}/calls/{slot['id']}/feedback", headers=bearer(s), json={"took_place": True, "rating": 5})
    assert r.status_code == 200 and r.json()["outcome"] == "held" and r.json()["rating"] == 5
    again = await client.post(f"{API}/calls/{slot['id']}/feedback", headers=bearer(s), json={"took_place": False})
    assert again.json()["outcome"] == "held"  # the first answer stands
    view = await open_slots(client, s)
    assert view["upcoming"] == [] and view["past"][0]["outcome"] == "held" and view["can_book"] is True
    past = (await client.get(f"{API}/teachers/me/calls", headers=bearer(t))).json()["past"]
    assert past[0]["outcome"] == "held" and past[0]["rating"] == 5
    kinds = {e["type"] async for e in db["events"].find({})}
    assert {"career_call_booked", "career_call_held"} <= kinds


async def test_a_call_that_did_not_happen_is_recorded_without_a_rating(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    s, _ = await learner(client, clock, db, PHONES[1])
    slot = (await add(client, t, body(clock))).json()
    assert (await book(client, s, slot["id"])).status_code == 200
    clock.advance(60 * 60 * 24)
    s = await sign_in(client, clock, PHONES[1])
    r = await client.post(f"{API}/calls/{slot['id']}/feedback", headers=bearer(s), json={"took_place": False, "rating": 4})
    assert r.status_code == 200 and r.json()["outcome"] == "missed" and r.json()["rating"] is None


# ---------------------------------------------------------------------------
# Who can touch what
# ---------------------------------------------------------------------------


async def test_nobody_can_act_on_a_call_that_is_not_theirs(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    other_t, _ = await host(client, clock, db, PHONES[3])
    a, _ = await learner(client, clock, db, PHONES[1])
    b, _ = await learner(client, clock, db, PHONES[2], name="Asha")
    slot = (await add(client, t, body(clock))).json()
    assert (await book(client, a, slot["id"])).status_code == 200
    assert (await client.post(f"{API}/teachers/me/calls/slots/{slot['id']}/cancel", headers=bearer(other_t))).status_code == 404
    assert (await client.post(f"{API}/calls/{slot['id']}/cancel", headers=bearer(b))).status_code == 404
    clock.advance(60 * 60 * 24)
    b, other_t = await sign_in(client, clock, PHONES[2]), await sign_in(client, clock, PHONES[3])
    assert (await client.post(f"{API}/calls/{slot['id']}/feedback", headers=bearer(b), json={"took_place": True})).status_code == 404
    assert (await client.get(f"{API}/teachers/me/calls", headers=bearer(other_t))).json()["upcoming"] == []


async def test_roles_are_kept_apart(client, clock, db):
    t, _ = await host(client, clock, db, PHONES[0])
    s, _ = await learner(client, clock, db, PHONES[1])
    assert (await client.get(f"{API}/calls", headers=bearer(t))).status_code == 403
    assert (await client.get(f"{API}/teachers/me/calls", headers=bearer(s))).status_code == 403
    assert (await client.get(f"{API}/calls")).status_code == 401
