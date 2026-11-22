"""Student and teacher profiles: validation, guardian consent, roles and isolation."""
from tests.conftest import OTHER_PHONE, STUDENT, TEACHER, bearer, sign_in

API = "/api/v1"


# --- catalog --------------------------------------------------------------


async def test_districts_catalog_has_all_36(client):
    r = await client.get(f"{API}/catalog/districts")
    districts = r.json()["districts"]
    assert r.json()["state"] == "Maharashtra" and len(districts) == 36
    assert len({d["id"] for d in districts}) == 36
    assert all(d["en"] and d["hi"] and d["mr"] for d in districts)
    assert "pune" in {d["id"] for d in districts}


# --- students -------------------------------------------------------------


async def test_student_profile_is_created_and_readable(client, clock):
    tokens = await sign_in(client, clock)
    r = await client.post(f"{API}/students/profile", headers=bearer(tokens), json=STUDENT)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Priya" and body["age_band"] == "16-18" and body["state"] == "Maharashtra"
    assert body["guardian_consent"] is True and body["guardian_consent_at"] is not None
    got = await client.get(f"{API}/students/me", headers=bearer(tokens))
    assert got.status_code == 200 and got.json()["district"] == "pune"


async def test_under_18_needs_guardian_consent(client, clock):
    tokens = await sign_in(client, clock)
    r = await client.post(f"{API}/students/profile", headers=bearer(tokens), json={**STUDENT, "guardian_consent": False})
    assert r.status_code == 422 and r.json()["code"] == "guardian_consent_required"
    # and nothing was created
    assert (await client.get(f"{API}/me", headers=bearer(tokens))).json()["profile"] is None


async def test_adults_do_not_need_guardian_consent(client, clock):
    tokens = await sign_in(client, clock)
    r = await client.post(
        f"{API}/students/profile", headers=bearer(tokens), json={**STUDENT, "age": 21, "grade": 13, "guardian_consent": False}
    )
    assert r.status_code == 201 and r.json()["age_band"] == "18+" and r.json()["guardian_consent"] is False


async def test_age_bands(client, clock):
    tokens = await sign_in(client, clock)
    r = await client.post(f"{API}/students/profile", headers=bearer(tokens), json={**STUDENT, "age": 14, "grade": 9})
    assert r.json()["age_band"] == "14-16"


async def test_invalid_student_fields_are_rejected(client, clock):
    tokens = await sign_in(client, clock)
    for bad in (
        {"district": "atlantis"},
        {"grade": 8},
        {"grade": 15},
        {"age": 5},
        {"name": "   "},
        {"block": ""},
        {"state": "Kerala"},
    ):
        r = await client.post(f"{API}/students/profile", headers=bearer(tokens), json={**STUDENT, **bad})
        assert r.status_code == 422, bad


async def test_a_second_profile_is_refused(client, clock):
    tokens = await sign_in(client, clock)
    await client.post(f"{API}/students/profile", headers=bearer(tokens), json=STUDENT)
    r = await client.post(f"{API}/students/profile", headers=bearer(tokens), json=STUDENT)
    assert r.status_code == 409 and r.json()["code"] == "profile_exists"


async def test_profile_creation_requires_a_session(client):
    r = await client.post(f"{API}/students/profile", json=STUDENT)
    assert r.status_code == 401


async def test_student_profile_can_be_edited(client, clock):
    tokens = await sign_in(client, clock)
    await client.post(f"{API}/students/profile", headers=bearer(tokens), json=STUDENT)
    r = await client.patch(f"{API}/students/me", headers=bearer(tokens), json={"block": "Mulshi", "grade": 11})
    assert r.status_code == 200 and r.json()["block"] == "Mulshi" and r.json()["grade"] == 11
    assert r.json()["name"] == "Priya"  # untouched fields stay


async def test_editing_age_below_18_without_consent_is_refused(client, clock):
    tokens = await sign_in(client, clock)
    await client.post(f"{API}/students/profile", headers=bearer(tokens), json={**STUDENT, "age": 21, "grade": 13, "guardian_consent": False})
    r = await client.patch(f"{API}/students/me", headers=bearer(tokens), json={"age": 17})
    assert r.status_code == 422 and r.json()["code"] == "guardian_consent_required"
    ok = await client.patch(f"{API}/students/me", headers=bearer(tokens), json={"age": 17, "guardian_consent": True})
    assert ok.status_code == 200 and ok.json()["age_band"] == "16-18"


async def test_consent_timestamp_is_kept_when_other_fields_change(client, clock):
    tokens = await sign_in(client, clock)
    created = (await client.post(f"{API}/students/profile", headers=bearer(tokens), json=STUDENT)).json()
    clock.advance(600)  # later, but inside the 15-minute access token
    edited = (await client.patch(f"{API}/students/me", headers=bearer(tokens), json={"block": "Mulshi"})).json()
    assert edited["guardian_consent_at"] == created["guardian_consent_at"]


# --- teachers -------------------------------------------------------------


async def test_teacher_profile_is_created_unverified(client, clock):
    tokens = await sign_in(client, clock)
    r = await client.post(f"{API}/teachers/profile", headers=bearer(tokens), json=TEACHER)
    assert r.status_code == 201
    body = r.json()
    assert body["roles"] == ["teacher", "mentor"] and body["languages"] == ["mr", "hi"]
    assert body["tier"] == 0 and body["trust"] is None and body["capacity"] == {"limit": 0, "free": 0}
    assert body["skills"] == [
        {"tag": "sewing_machine", "level": None, "verified": False},
        {"tag": "tailoring", "level": None, "verified": False},
    ]
    assert (await client.get(f"{API}/me", headers=bearer(tokens))).json()["profile"] == "teacher"


async def test_teacher_duplicates_are_collapsed(client, clock):
    tokens = await sign_in(client, clock)
    r = await client.post(
        f"{API}/teachers/profile", headers=bearer(tokens),
        json={**TEACHER, "roles": ["expert", "expert"], "languages": ["hi", "hi"], "skills": ["Tailoring", "tailoring"]},
    )
    assert r.json()["roles"] == ["expert"] and r.json()["languages"] == ["hi"] and len(r.json()["skills"]) == 1


async def test_invalid_teacher_fields_are_rejected(client, clock):
    tokens = await sign_in(client, clock)
    for bad in (
        {"roles": []},
        {"roles": ["principal"]},
        {"languages": []},
        {"languages": ["fr"]},
        {"weekly_hours": 0},
        {"weekly_hours": 99},
        {"skills": ["!!"]},
        {"district": "atlantis"},
    ):
        r = await client.post(f"{API}/teachers/profile", headers=bearer(tokens), json={**TEACHER, **bad})
        assert r.status_code == 422, bad


async def test_editing_skills_keeps_existing_entries(client, clock, db):
    tokens = await sign_in(client, clock)
    await client.post(f"{API}/teachers/profile", headers=bearer(tokens), json={**TEACHER, "skills": ["sewing", "tailoring"]})
    # the skill check was passed and the evidence approved, which is what makes "sewing" verified
    await db["teacher_profiles"].update_one({}, {"$set": {"passed_areas": ["tailoring"], "evidence.status": "verified", "skills.0.level": 3}})
    r = await client.patch(f"{API}/teachers/me", headers=bearer(tokens), json={"skills": ["sewing", "embroidery"]})
    skills = {s["tag"]: s for s in r.json()["skills"]}
    assert skills["sewing"] == {"tag": "sewing", "level": 3, "verified": True}
    assert skills["embroidery"] == {"tag": "embroidery", "level": None, "verified": False}


async def test_dropping_a_proven_skill_from_the_list_does_not_lose_it(client, clock, db):
    tokens = await sign_in(client, clock)
    await client.post(f"{API}/teachers/profile", headers=bearer(tokens), json={**TEACHER, "skills": ["sewing"]})
    await db["teacher_profiles"].update_one({}, {"$set": {"passed_areas": ["tailoring"], "evidence.status": "verified", "tier": 1}})
    r = await client.patch(f"{API}/teachers/me", headers=bearer(tokens), json={"skills": ["embroidery"]})
    assert {"tag": "sewing", "level": None, "verified": True} in r.json()["skills"]


# --- roles and isolation --------------------------------------------------


async def test_one_account_cannot_be_both_student_and_teacher(client, clock):
    tokens = await sign_in(client, clock)
    await client.post(f"{API}/students/profile", headers=bearer(tokens), json=STUDENT)
    r = await client.post(f"{API}/teachers/profile", headers=bearer(tokens), json=TEACHER)
    assert r.status_code == 409 and r.json()["code"] == "role_conflict"


async def test_student_cannot_use_teacher_endpoints(client, clock):
    tokens = await sign_in(client, clock)
    await client.post(f"{API}/students/profile", headers=bearer(tokens), json=STUDENT)
    for method, path in (("get", "/teachers/me"), ("patch", "/teachers/me")):
        r = await getattr(client, method)(f"{API}{path}", headers=bearer(tokens), **({"json": {}} if method == "patch" else {}))
        assert r.status_code == 403 and r.json()["code"] == "wrong_role"


async def test_teacher_cannot_use_student_endpoints(client, clock):
    tokens = await sign_in(client, clock)
    await client.post(f"{API}/teachers/profile", headers=bearer(tokens), json=TEACHER)
    assert (await client.get(f"{API}/students/me", headers=bearer(tokens))).status_code == 403


async def test_each_user_only_ever_sees_their_own_profile(client, clock):
    a = await sign_in(client, clock)
    b = await sign_in(client, clock, OTHER_PHONE)
    await client.post(f"{API}/students/profile", headers=bearer(a), json={**STUDENT, "name": "Priya"})
    await client.post(f"{API}/students/profile", headers=bearer(b), json={**STUDENT, "name": "Ramesh", "age": 22, "grade": 14, "guardian_consent": False})
    assert (await client.get(f"{API}/students/me", headers=bearer(a))).json()["name"] == "Priya"
    assert (await client.get(f"{API}/students/me", headers=bearer(b))).json()["name"] == "Ramesh"
    await client.patch(f"{API}/students/me", headers=bearer(b), json={"name": "Changed"})
    assert (await client.get(f"{API}/students/me", headers=bearer(a))).json()["name"] == "Priya"
