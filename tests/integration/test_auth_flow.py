"""End-to-end: create user → login → get token → call protected endpoint.

Also covers first-login password-change enforcement (ARCHITECTURE_REVIEW §B-7).
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import requires_docker

pytestmark = [pytest.mark.integration, requires_docker]


@pytest.mark.asyncio
async def test_login_initial_password_requires_change(api_client, db_session):
    """Seed a user with password_changed_at = NULL and verify the login
    response flag is set."""
    from sia.auth.password import hash_password
    from sia.models.user import User

    db_session.add(User(
        username="alice_init",
        email="alice_init@example.com",
        display_name="Alice",
        hashed_password=hash_password("InitialPass1!"),
        role="analyst",
        auth_provider="local",
        status="active",
        password_changed_at=None,
    ))
    await db_session.commit()

    resp = await api_client.post(
        "/api/v1/auth/login",
        json={"username": "alice_init", "password": "InitialPass1!",
              "provider": "local"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["password_change_required"] is True
    assert "access_token" in body


@pytest.mark.asyncio
async def test_after_password_change_flag_clears(api_client, db_session):
    """Once password_changed_at is set, login no longer asks to change."""
    from datetime import datetime

    from sia.auth.password import hash_password
    from sia.models.user import User

    db_session.add(User(
        username="bob",
        email="bob@example.com",
        display_name="Bob",
        hashed_password=hash_password("ChangedLater1!"),
        role="viewer",
        auth_provider="local",
        status="active",
        password_changed_at=datetime.now(),
    ))
    await db_session.commit()

    resp = await api_client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "ChangedLater1!",
              "provider": "local"},
    )
    assert resp.status_code == 200
    assert resp.json()["password_change_required"] is False


@pytest.mark.asyncio
async def test_bad_password_increments_lockout_counter(api_client, db_session):
    """Verify the fail-commit path does not roll back failed_login_count."""
    from sia.auth.password import hash_password
    from sia.models.user import User

    db_session.add(User(
        username="carol",
        email="carol@example.com",
        display_name="Carol",
        hashed_password=hash_password("Correct1!"),
        role="viewer",
        auth_provider="local",
        status="active",
    ))
    await db_session.commit()

    # 3 wrong attempts
    for _ in range(3):
        resp = await api_client.post(
            "/api/v1/auth/login",
            json={"username": "carol", "password": "Wrong1!",
                  "provider": "local"},
        )
        assert resp.status_code == 401

    from sqlalchemy import select
    from sia.models.user import User as U
    row = (await db_session.execute(
        select(U).where(U.username == "carol")
    )).scalar_one()
    assert row.failed_login_count == 3
