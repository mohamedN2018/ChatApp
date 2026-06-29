"""Unit tests for the custom User model and manager."""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_create_user_normalises_email_and_sets_password():
    user = User.objects.create_user(
        email="Alice@Example.COM", password="s3cretpw123", username="alice"
    )
    assert user.email == "alice@example.com"
    assert user.check_password("s3cretpw123")
    assert isinstance(user.id, uuid.UUID)
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_email_verified is False
    # display_name defaults to the username when not provided.
    assert user.display_name == "alice"


def test_create_user_requires_email():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="x", username="nobody")


def test_create_superuser_flags():
    admin = User.objects.create_superuser(
        email="root@example.com", password="rootpw12345", username="root"
    )
    assert admin.is_staff and admin.is_superuser and admin.is_active
    assert admin.is_email_verified is True


def test_email_is_unique_case_insensitively():
    User.objects.create_user(email="bob@example.com", password="pw123456789", username="bob")
    with pytest.raises((IntegrityError, ValidationError)):
        User.objects.create_user(email="BOB@example.com", password="pw123456789", username="bob2")


def test_invalid_username_rejected():
    with pytest.raises(ValidationError):
        User.objects.create_user(
            email="c@example.com", password="pw123456789", username="no spaces!"
        )


def test_soft_delete_deactivates_without_removing_row():
    user = User.objects.create_user(email="d@example.com", password="pw123456789", username="dan")
    user.soft_delete()
    user.refresh_from_db()
    assert user.is_active is False
    assert user.deleted_at is not None
    assert User.objects.filter(pk=user.pk).exists()  # row still present


def test_str_representation():
    user = User.objects.create_user(email="e@example.com", password="pw123456789", username="eve")
    assert str(user) == "@eve <e@example.com>"
