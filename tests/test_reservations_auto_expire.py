from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.reservation_service import expire_unapproved_reservations
from app.utils.statuses import ReservationStatus


def _reservation_stub(*, reservation_id: int, start_dt: datetime, status: str = ReservationStatus.PENDING):
    return SimpleNamespace(
        id=reservation_id,
        user_id=100 + reservation_id,
        date=start_dt.date(),
        start_time=start_dt.time().replace(microsecond=0),
        status=status,
        admin_note=None,
    )


def test_expire_unapproved_reservations_cancels_only_expired_pending():
    now = datetime(2026, 4, 12, 7, 0, 0)
    expired = _reservation_stub(reservation_id=1, start_dt=now - timedelta(minutes=5))
    future = _reservation_stub(reservation_id=2, start_dt=now + timedelta(minutes=30))

    fake_query = MagicMock()
    fake_query.filter.return_value.all.return_value = [expired, future]
    fake_reservation_model = MagicMock()
    fake_reservation_model.query = fake_query
    fake_reservation_model.status = ReservationStatus.PENDING

    with (
        patch("app.services.reservation_service.Reservation", fake_reservation_model),
        patch("app.services.reservation_service.build_notification") as notification_mock,
        patch("app.services.reservation_service.log_event") as log_event_mock,
        patch("app.services.reservation_service.db.session.commit") as commit_mock,
        patch("app.services.reservation_service.url_for", return_value="/reservations/my"),
    ):
        expired_count = expire_unapproved_reservations(now_dt=now)

    assert expired_count == 1
    assert expired.status == ReservationStatus.CANCELLED
    assert expired.admin_note == "Cancelada por falta de confirmación"
    assert future.status == ReservationStatus.PENDING
    notification_mock.assert_called_once()
    log_event_mock.assert_called_once()
    commit_mock.assert_called_once()


def test_expire_unapproved_reservations_no_changes_no_commit():
    now = datetime(2026, 4, 12, 7, 0, 0)
    future_pending = _reservation_stub(reservation_id=3, start_dt=now + timedelta(hours=1))

    fake_query = MagicMock()
    fake_query.filter.return_value.all.return_value = [future_pending]
    fake_reservation_model = MagicMock()
    fake_reservation_model.query = fake_query
    fake_reservation_model.status = ReservationStatus.PENDING

    with (
        patch("app.services.reservation_service.Reservation", fake_reservation_model),
        patch("app.services.reservation_service.build_notification") as notification_mock,
        patch("app.services.reservation_service.log_event") as log_event_mock,
        patch("app.services.reservation_service.db.session.commit") as commit_mock,
        patch("app.services.reservation_service.url_for", return_value="/reservations/my"),
    ):
        expired_count = expire_unapproved_reservations(now_dt=now)

    assert expired_count == 0
    assert future_pending.status == ReservationStatus.PENDING
    notification_mock.assert_not_called()
    log_event_mock.assert_not_called()
    commit_mock.assert_not_called()
