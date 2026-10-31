import asyncio
import io
import uuid
from datetime import timedelta

import pytest
from PIL import Image
from sqlalchemy import select

from app.config import settings
from app.models.admin_log import AdminLog
from app.models.student_verification import StudentIdentityClaim, StudentVerification, StudentVerificationChallenge
from app.models.user import User
from app.services.student_verification import cleanup_expired_verifications, fingerprint, normalize_student_id, utcnow
from app.utils.security import create_access_token
from app.utils.verification_storage import VerificationStorage, sanitize_proof_image
from tests.conftest import TestSession

BASE = "/api/v1/student-verifications"
ADMIN = "/api/v1/admin/student-verifications"


@pytest.fixture(autouse=True)
def verification_config(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STUDENT_VERIFICATION_ENABLED", True)
    monkeypatch.setattr(settings, "VERIFICATION_FINGERPRINT_KEY", "verification-test-key-" + "x" * 40)
    monkeypatch.setattr(settings, "VERIFICATION_FINGERPRINT_KEY_VERSION", "v1")
    monkeypatch.setattr(settings, "VERIFICATION_FINGERPRINT_PREVIOUS_KEYS", "{}")
    monkeypatch.setattr(settings, "VERIFICATION_PRIVATE_DIR", str(tmp_path / "private"))
    monkeypatch.setattr(settings, "VERIFICATION_STORAGE_PROVIDER", "local")
    monkeypatch.setattr(settings, "VERIFICATION_SCHOOL_ID", "pilot")
    monkeypatch.setattr(settings, "VERIFICATION_SCHOOL_NAME", "试点学校")


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def photo():
    output = io.BytesIO()
    Image.new("RGB", (320, 240), "white").save(output, "PNG")
    return output.getvalue()


async def challenge(client, token):
    response = await client.post(BASE + "/challenge", headers=headers(token))
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def submit(client, token, challenge_data, student_id="20260001", content=None):
    response = await client.post(BASE, headers=headers(token), data={
        "verification_id": challenge_data["verification_id"],
        "challenge_code": challenge_data["code"], "student_id": student_id, "consent_version": "student-card-v1",
    }, files={"file": ("proof.png", photo() if content is None else content, "image/png")})
    return response


def approval(student_id="20260001"):
    return {"decision": "approved", "challenge_matches": True, "school_matches": True,
            "student_number_matches": True, "validity_checked": True, "student_id": student_id}


async def test_disabled_verification_fails_closed(client, guest_token, monkeypatch):
    monkeypatch.setattr(settings, "STUDENT_VERIFICATION_ENABLED", False)
    response = await client.post(BASE + "/challenge", headers=headers(guest_token))
    assert response.status_code == 503


async def test_challenge_bound_to_account_and_single_use(client, guest_token, student_token):
    data = await challenge(client, guest_token)
    assert len(data["code"]) == 6
    wrong_owner = await submit(client, student_token, data)
    assert wrong_owner.status_code == 404
    response = await submit(client, guest_token, data)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "pending"
    replay = await submit(client, guest_token, data)
    assert replay.status_code == 409
    async with TestSession() as db:
        row = await db.get(StudentVerification, uuid.UUID(data["verification_id"]))
        assert row.consent_version == "student-card-v1" and row.consented_at
        assert row.student_fingerprint != "20260001"
        assert row.student_fingerprint == fingerprint("20260001", "pilot", settings.VERIFICATION_FINGERPRINT_KEY)
        assert row.proof_key and not row.proof_key.startswith("/static")
        assert not hasattr(row, "student_id") and not hasattr(row, "real_name")


async def test_expired_challenge_and_new_code_invalidates_old_draft(client, guest_token):
    first = await challenge(client, guest_token)
    await challenge(client, guest_token)
    assert (await submit(client, guest_token, first)).status_code == 409
    third = await challenge(client, guest_token)
    async with TestSession() as db:
        row = await db.get(StudentVerificationChallenge, uuid.UUID(third["challenge_id"]))
        row.expires_at = utcnow() - timedelta(seconds=1)
        await db.commit()
    assert (await submit(client, guest_token, third)).status_code == 409


async def test_fake_and_small_images_rejected_without_consuming_code(client, guest_token):
    data = await challenge(client, guest_token)
    response = await submit(client, guest_token, data, content=b"<script>fake</script>")
    assert response.status_code == 400
    assert (await submit(client, guest_token, data)).status_code == 200


async def test_only_admin_can_view_private_proof_and_access_is_audited(client, guest_token, console_headers):
    data = await challenge(client, guest_token)
    await submit(client, guest_token, data)
    evidence = ADMIN + f"/{data['verification_id']}/evidence"
    assert (await client.get(evidence, headers=headers(guest_token))).status_code == 403
    response = await client.get(evidence, headers=console_headers)
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["content-type"].startswith("image/jpeg")
    async with TestSession() as db:
        logs = (await db.scalars(select(AdminLog).where(AdminLog.action == "verification.evidence_view"))).all()
        assert len(logs) == 1
        assert logs[0].target_id == data["verification_id"]
        row = await db.get(StudentVerification, uuid.UUID(data["verification_id"]))
        assert (await client.get("/static/" + row.proof_key)).status_code == 404


async def test_approval_checks_photo_student_number_and_expiry(client, guest_user, guest_token, console_headers):
    data = await challenge(client, guest_token)
    await submit(client, guest_token, data)
    url = ADMIN + f"/{data['verification_id']}/review"
    bad = await client.post(url, headers=console_headers, json=approval("20269999"))
    assert bad.status_code == 400
    missing = approval()
    missing["challenge_matches"] = False
    assert (await client.post(url, headers=console_headers, json=missing)).status_code == 400
    expires = (utcnow() + timedelta(days=30)).date()
    response = await client.post(url, headers=console_headers,
                                 json={**approval(), "card_valid_until": expires.isoformat()})
    assert response.status_code == 200, response.text
    async with TestSession() as db:
        user = await db.get(User, guest_user.id)
        record = await db.get(StudentVerification, uuid.UUID(data["verification_id"]))
        assert user.is_verified and user.role == "student"
        assert user.verified_until == record.verified_until
        assert user.verified_until <= utcnow() + timedelta(days=32)
        assert await db.scalar(select(StudentIdentityClaim.id).where(StudentIdentityClaim.user_id == user.id))
        assert user.student_id is None and user.real_name is None
    assert (await client.post(url, headers=console_headers, json=approval())).status_code == 409


async def test_same_school_student_id_conflict_is_generic(client, guest_token, student_user, console_headers):
    first = await challenge(client, guest_token)
    await submit(client, guest_token, first)
    assert (await client.post(ADMIN + f"/{first['verification_id']}/review",
                             headers=console_headers, json=approval())).status_code == 200
    other = create_access_token({"sub": str(student_user.id), "role": "student"})
    second = await challenge(client, other)
    response = await submit(client, other, second)
    assert response.status_code == 409
    text = response.text
    assert str(student_user.id) not in text
    assert "资料" in text and "绑定到" not in text


async def test_rejected_proof_deleted_after_seven_days(client, guest_token, console_headers):
    data = await challenge(client, guest_token)
    await submit(client, guest_token, data)
    response = await client.post(ADMIN + f"/{data['verification_id']}/review", headers=console_headers,
                                 json={"decision": "rejected", "reason": "拍摄码不清晰，请重新拍摄"})
    assert response.status_code == 200
    async with TestSession() as db:
        record = await db.get(StudentVerification, uuid.UUID(data["verification_id"]))
        key = record.proof_key
        assert record.evidence_delete_after > utcnow() + timedelta(days=6)
        record.evidence_delete_after = utcnow() - timedelta(seconds=1)
        await db.commit()
        result = await cleanup_expired_verifications(db)
        assert result["evidence_deleted"] == 1
        assert record.proof_key is None and record.evidence_deleted_at
        assert not VerificationStorage()._path(key).exists()
    response = await client.get(ADMIN + f"/{data['verification_id']}/evidence", headers=console_headers)
    assert response.status_code == 404


async def test_pending_fourteen_days_expires_and_deletes_evidence(client, guest_token):
    data = await challenge(client, guest_token)
    await submit(client, guest_token, data)
    async with TestSession() as db:
        record = await db.get(StudentVerification, uuid.UUID(data["verification_id"]))
        record.submitted_at = utcnow() - timedelta(days=15)
        record.evidence_delete_after = record.submitted_at + timedelta(days=14)
        await db.commit()
        result = await cleanup_expired_verifications(db)
        assert result["expired"] == 1 and result["evidence_deleted"] == 1
        assert record.status == "expired" and not record.proof_key


async def test_revocation_removes_verified_access(client, guest_user, guest_token, console_headers):
    data = await challenge(client, guest_token)
    await submit(client, guest_token, data)
    await client.post(ADMIN + f"/{data['verification_id']}/review", headers=console_headers, json=approval())
    response = await client.post(ADMIN + f"/{data['verification_id']}/revoke", headers=console_headers,
                                 json={"reason": "证件有效性复核未通过"})
    assert response.status_code == 200
    async with TestSession() as db:
        user = await db.get(User, guest_user.id)
        assert not user.is_verified and user.role == "guest" and user.verified_until is None


async def test_historical_key_claim_blocks_duplicate_after_rotation(client, guest_token):
    old_key = "old-independent-key-" + "x" * 40
    old_owner_id = uuid.uuid4()
    async with TestSession() as db:
        db.add(User(id=old_owner_id, openid="old_owner", nickname="历史账号", role="guest"))
        await db.flush()
        db.add(StudentIdentityClaim(user_id=old_owner_id, school_id="pilot",
            student_fingerprint=fingerprint("20260001", "pilot", old_key), fingerprint_key_version="old"))
        await db.commit()
    settings.VERIFICATION_FINGERPRINT_PREVIOUS_KEYS = '{"old":"' + old_key + '"}'
    data = await challenge(client, guest_token)
    response = await submit(client, guest_token, data)
    assert response.status_code == 409


def test_private_storage_rejects_public_directory(monkeypatch):
    monkeypatch.setattr(settings, "VERIFICATION_PRIVATE_DIR", settings.STATIC_BASE_DIR + "/proofs")
    with pytest.raises(RuntimeError):
        VerificationStorage()


def test_image_sanitization_and_student_id_normalization():
    output = sanitize_proof_image(photo())
    assert output.startswith(b"\xff\xd8")
    with Image.open(io.BytesIO(output)) as image:
        assert not image.getexif() and image.format == "JPEG"
    assert normalize_student_id(" 2026 0001 ") == "20260001"

async def test_parallel_approvals_cannot_bind_same_student_twice(client, guest_token, student_token, console_headers):
    first = await challenge(client, guest_token)
    second = await challenge(client, student_token)
    assert (await submit(client, guest_token, first)).status_code == 200
    assert (await submit(client, student_token, second)).status_code == 200
    results = await asyncio.gather(*[
        client.post(ADMIN + f"/{item['verification_id']}/review",
                    headers=console_headers, json=approval()) for item in [first, second]
    ])
    assert sorted(response.status_code for response in results) == [200, 409]
    async with TestSession() as db:
        claims = (await db.scalars(select(StudentIdentityClaim))).all()
        assert len(claims) == 1

async def test_missing_evidence_after_backup_restore_returns_404(client, guest_token, console_headers):
    data = await challenge(client, guest_token)
    await submit(client, guest_token, data)
    async with TestSession() as db:
        row = await db.get(StudentVerification, uuid.UUID(data["verification_id"]))
        await VerificationStorage().delete(row.proof_key)
    response = await client.get(ADMIN + f"/{data['verification_id']}/evidence", headers=console_headers)
    assert response.status_code == 404


async def test_orphan_evidence_older_than_fourteen_days_is_deleted():
    import os
    storage = VerificationStorage()
    key = f"evidence/{uuid.uuid4()}/{uuid.uuid4().hex}.jpg"
    await storage.save(key, sanitize_proof_image(photo()))
    old = (utcnow() - timedelta(days=15)).timestamp()
    os.utime(storage._path(key), (old, old))
    async with TestSession() as db:
        result = await cleanup_expired_verifications(db)
    assert result["orphans_deleted"] == 1
    assert not storage._path(key).exists()


def test_cos_deletion_purges_only_exact_key_versions_and_markers():
    from unittest.mock import MagicMock
    storage = VerificationStorage()
    client = MagicMock()
    key = f"evidence/{uuid.uuid4()}/{uuid.uuid4().hex}.jpg"
    client.get_paginator.return_value.paginate.return_value = [
        {"Versions": [{"Key": key, "VersionId": "v1"},
                      {"Key": key + "-other", "VersionId": "neighbor"}],
         "DeleteMarkers": [{"Key": key, "VersionId": "deleted"}]},
        {"Versions": [{"Key": key, "VersionId": "v0"}]},
    ]
    client.delete_objects.return_value = {}
    storage._delete_cos_versions(client, key)
    removed = client.delete_objects.call_args.kwargs["Delete"]["Objects"]
    assert removed == [{"Key": key, "VersionId": "v1"}, {"Key": key, "VersionId": "deleted"},
                       {"Key": key, "VersionId": "v0"}]
    assert all(item["Key"] == key for item in removed)


def test_cos_private_bucket_refuses_version_backup():
    from unittest.mock import MagicMock
    from botocore.exceptions import ClientError
    storage = VerificationStorage()
    client = MagicMock()
    client.get_bucket_acl.return_value = {"Grants": []}
    client.get_bucket_policy.side_effect = ClientError({"Error": {"Code": "NoSuchBucketPolicy"}}, "GetBucketPolicy")
    client.get_bucket_versioning.return_value = {"Status": "Enabled"}
    with pytest.raises(RuntimeError, match="版本"):
        storage._validate_cos_privacy(client)


def test_cos_never_versioned_object_is_physically_deleted():
    from unittest.mock import MagicMock
    storage = VerificationStorage()
    client = MagicMock()
    key = f"evidence/{uuid.uuid4()}/{uuid.uuid4().hex}.jpg"
    client.get_paginator.return_value.paginate.return_value = [{}]
    client.get_bucket_versioning.return_value = {}
    storage._delete_cos_versions(client, key)
    client.delete_object.assert_called_once_with(Bucket=settings.VERIFICATION_COS_BUCKET, Key=key)


def test_cos_suspended_bucket_does_not_create_new_delete_marker():
    from unittest.mock import MagicMock
    storage = VerificationStorage()
    client = MagicMock()
    key = f"evidence/{uuid.uuid4()}/{uuid.uuid4().hex}.jpg"
    client.get_paginator.return_value.paginate.return_value = [{}]
    client.get_bucket_versioning.return_value = {"Status": "Suspended"}
    storage._delete_cos_versions(client, key)
    client.delete_object.assert_not_called()
