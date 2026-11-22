"""Ordinary (non-search) indexes. Search and vector indexes live in scripts/create_indexes.py."""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db["users"].create_index("phone_hash", unique=True)

    # TTL indexes: MongoDB deletes expired documents on its own.
    await db["otp_requests"].create_index("expires_at", expireAfterSeconds=0)
    await db["otp_requests"].create_index([("phone_hash", 1), ("created_at", -1)])
    await db["otp_requests"].create_index([("ip", 1), ("created_at", -1)])

    await db["refresh_tokens"].create_index("token_hash", unique=True)
    await db["refresh_tokens"].create_index("expires_at", expireAfterSeconds=0)
    await db["refresh_tokens"].create_index("family_id")
    await db["refresh_tokens"].create_index("user_id")

    await db["student_profiles"].create_index("user_id", unique=True)
    await db["student_profiles"].create_index([("block", 1), ("grade", 1)])
    await db["teacher_profiles"].create_index("user_id", unique=True)

    await db["intake_sessions"].create_index([("user_id", 1), ("created_at", -1)])
    await db["assessments"].create_index([("user_id", 1), ("created_at", -1)])
    await db["journeys"].create_index([("student_id", 1), ("created_at", -1)])
    await db["journeys"].create_index([("teacher_id", 1), ("state", 1)])
    await db["matches"].create_index([("journey_id", 1), ("created_at", -1)])
    await db["matches"].create_index([("teacher_id", 1), ("status", 1), ("created_at", 1)])
    await db["matches"].create_index([("status", 1), ("expires_at", 1)])
    await db["teacher_tests"].create_index([("user_id", 1), ("area_id", 1)])
    await db["teacher_profiles"].create_index([("evidence.status", 1), ("evidence.submitted_at", 1)])
    await db["events"].create_index([("type", 1), ("ts", -1)])

    await db["assignments"].create_index([("journey_id", 1), ("milestone", 1), ("status", 1)])
    # one attempt number per learner and assignment, so two taps at once cannot make two drafts
    await db["submissions"].create_index([("assignment_id", 1), ("student_id", 1), ("attempt", 1)], unique=True)
    await db["submissions"].create_index([("journey_id", 1), ("status", 1), ("sent_at", 1)])
    await db["submission_photos"].create_index("submission_id")

    # M8: one application per learner and programme, so two taps at once make one
    await db["applications"].create_index([("student_id", 1), ("opportunity_id", 1)], unique=True)
    await db["applications"].create_index([("journey_id", 1), ("status", 1), ("created_at", 1)])
    await db["notifications"].create_index([("user_id", 1), ("created_at", -1)])
    await db["notifications"].create_index([("user_id", 1), ("read_at", 1)])

    # career calls: open times for a path, a mentor's own times, and a learner's bookings
    await db["calls"].create_index([("career_id", 1), ("status", 1), ("starts_at", 1)])
    await db["calls"].create_index([("teacher_id", 1), ("starts_at", 1)])
    await db["calls"].create_index([("student_id", 1), ("status", 1)])

    # connect (adult learners): one card per learner, one connection record per pair, and blocks
    await db["connect_profiles"].create_index([("user_id", 1)], unique=True)
    await db["connect_profiles"].create_index([("visible", 1)])
    await db["connections"].create_index([("pair", 1)], unique=True)
    await db["connections"].create_index([("recipient", 1), ("status", 1)])
    await db["connections"].create_index([("requester", 1), ("created_at", -1)])
    await db["peer_blocks"].create_index([("by", 1), ("target", 1)], unique=True)
    await db["peer_blocks"].create_index([("target", 1)])
