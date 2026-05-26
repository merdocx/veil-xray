"""Сопоставление ошибок БД с HTTP-ответами."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError, TimeoutError as SATimeoutError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def raise_http_for_db_error(
    e: Exception,
    *,
    operation: str,
    default_detail: str,
    integrity_conflict_detail: str | None = None,
    db: "Session | None" = None,
) -> None:
    """Преобразует исключение БД в HTTPException (функция не возвращает значение)."""
    if db is not None:
        try:
            db.rollback()
        except Exception:
            pass
    if isinstance(e, SATimeoutError):
        logger.error(f"[DB_TIMEOUT] {operation}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please retry.",
        ) from e

    if isinstance(e, IntegrityError) and integrity_conflict_detail:
        logger.warning(f"[DB_INTEGRITY] {operation}: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=integrity_conflict_detail,
        ) from e

    logger.error(f"[DB_ERROR] {operation}: {e}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"{default_detail}: {str(e)}",
    ) from e
