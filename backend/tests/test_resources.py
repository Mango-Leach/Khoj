"""Learning resources: the data file, and how it reaches the career pages."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import pytest

from app.services import catalog, resources
from tests.conftest import STUDENT, bearer, sign_in

API = "/api/v1"
OFFICIAL_HOSTS = (
    "onlinecourses.swayam2.ac.in",
    "onlinecourses.nptel.ac.in",
    "www.nios.ac.in",
    "www.nsdcindia.org",
    "www.tsscindia.com",
    "www.skillindiadigital.gov.in",
)


def test_every_resource_is_a_real_link_to_a_known_provider_and_unverified():
    seen = set()
    for r in catalog.resources():
        assert r["id"] not in seen
        seen.add(r["id"])
        url = urlparse(r["url"])
        assert url.scheme == "https" and url.hostname in OFFICIAL_HOSTS, (r["id"], url.hostname)
        assert r["title"].strip() and r["provider"].strip()
        assert r["kind"] in {"mooc", "course", "curriculum"}
        assert r["access"] == "link_out"
        assert r["verified_on"] is None, "only a person may set verified_on"
        assert r["level"] in {None, "school", "diploma", "college"}
        assert r["cost"] in {None, "free", "free_certificate_fee"}
        assert set(r["languages"]) <= {"en", "hi", "mr"}
        assert r["career_ids"] and set(r["career_ids"]) <= catalog.career_ids()


def test_resources_never_state_a_money_figure():
    text = " ".join(f"{r['title']} {r['provider']}" for r in catalog.resources())
    assert not re.search(r"₹|\bRs\.?\s*\d|\d+\s*rupees", text, re.I)


def test_every_full_depth_career_has_at_least_two_courses():
    for c in catalog.careers():
        if c["depth"] == "full":
            assert len(catalog.resources_for(c["career_id"])) >= 2, c["career_id"]


def test_school_learners_have_a_school_level_option_where_one_exists():
    # a Class 9 to 12 learner should not be shown only college-level courses for these careers
    for cid in ("tailoring_enterprise", "electrician_wiring", "pump_motor_repair", "shop_accounting_gst"):
        assert any(r["level"] == "school" for r in catalog.resources_for(cid)), cid


def test_view_marks_awaiting_verification():
    v = resources.view(catalog.resources()[0])
    assert v["awaiting_verification"] is True and v["verified_on"] is None
    assert {"title", "provider", "url", "kind", "level", "languages"} <= set(v)


async def student(client, clock):
    tokens = await sign_in(client, clock)
    r = await client.post(f"{API}/students/profile", json=STUDENT, headers=bearer(tokens))
    assert r.status_code == 201, r.text
    return tokens


async def test_career_detail_carries_courses_and_portals(client, clock):
    tokens = await student(client, clock)
    r = await client.get(f"{API}/careers/electrician_wiring", headers=bearer(tokens))
    assert r.status_code == 200
    body = r.json()
    assert len(body["learn"]) >= 2 and all(x["awaiting_verification"] for x in body["learn"])
    assert body["portals"], "the provider home pages stay as a fallback"
    assert "learn_links" not in body


async def test_a_career_with_no_course_yet_still_has_its_portals(client, clock):
    tokens = await student(client, clock)
    body = (await client.get(f"{API}/careers/govt_exam_prep", headers=bearer(tokens))).json()
    assert body["learn"] == [] and body["portals"]


async def test_resources_endpoint_filters_by_career_and_needs_sign_in(client, clock):
    assert (await client.get(f"{API}/resources")).status_code == 401
    tokens = await student(client, clock)
    allr = (await client.get(f"{API}/resources", headers=bearer(tokens))).json()["resources"]
    one = (await client.get(f"{API}/resources?career_id=tailoring_enterprise", headers=bearer(tokens))).json()["resources"]
    assert len(allr) == len(catalog.resources()) and 0 < len(one) < len(allr)
    assert all(r["id"] for r in one)
    assert (await client.get(f"{API}/resources?career_id=nope", headers=bearer(tokens))).status_code == 404


@pytest.mark.parametrize("cid", [c["career_id"] for c in catalog.careers()])
def test_career_detail_view_builds_for_every_career(cid):
    from app.services import assessments

    d = assessments.career_detail(catalog.career(cid))
    assert isinstance(d["learn"], list) and isinstance(d["portals"], list)
