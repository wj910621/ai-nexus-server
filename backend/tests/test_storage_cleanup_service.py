"""Tests for the durable storage deletion outbox."""
from unittest.mock import MagicMock

import pytest

from app.models.storage_cleanup import PendingStorageDeletion
from app.services.storage_cleanup_service import retry_pending_storage_deletions


@pytest.mark.asyncio
async def test_retry_pending_storage_deletion_removes_successful_entry(
    db_session, monkeypatch
):
    entry = PendingStorageDeletion(path="/uploads/datasets/old.png")
    db_session.add(entry)
    await db_session.commit()

    delete = MagicMock(return_value=True)
    monkeypatch.setattr("app.services.storage_cleanup_service.storage.delete", delete)

    deleted, failed = await retry_pending_storage_deletions(db_session)
    assert (deleted, failed) == (1, 0)
    delete.assert_called_once_with("/uploads/datasets/old.png")
    assert await db_session.get(PendingStorageDeletion, entry.id) is None


@pytest.mark.asyncio
async def test_retry_pending_storage_deletion_retains_failure(
    db_session, monkeypatch
):
    entry = PendingStorageDeletion(path="/uploads/datasets/retry.png")
    db_session.add(entry)
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.storage_cleanup_service.storage.delete",
        MagicMock(side_effect=OSError("locked")),
    )

    deleted, failed = await retry_pending_storage_deletions(db_session)
    assert (deleted, failed) == (0, 1)
    retained = await db_session.get(PendingStorageDeletion, entry.id)
    assert retained.attempts == 1
    assert retained.last_error == "locked"
