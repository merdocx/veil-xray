"""Тесты для api.errors."""

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, TimeoutError as SATimeoutError

from api.errors import raise_http_for_db_error


def test_db_timeout_maps_to_503():
    with pytest.raises(HTTPException) as exc:
        raise_http_for_db_error(
            SATimeoutError("stmt", {}, None),
            operation="test",
            default_detail="failed",
        )
    assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_integrity_maps_to_409():
    with pytest.raises(HTTPException) as exc:
        raise_http_for_db_error(
            IntegrityError("stmt", {}, None),
            operation="test",
            default_detail="failed",
            integrity_conflict_detail="duplicate",
        )
    assert exc.value.status_code == status.HTTP_409_CONFLICT
