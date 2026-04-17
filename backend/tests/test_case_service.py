"""
Tests for Case Service
========================
Covers create_case(), add_note(), update_case() (status transitions), and
the implicit close_case behaviour when status is set to 'closed' or
'filed_sar'.  The database session and all collaborator services are
fully mocked.

Run with:
    pytest backend/tests/test_case_service.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from fastapi import HTTPException

from services.case_service import CaseService, _generate_case_number


@pytest.fixture
def service():
    return CaseService()


# ── Helpers ────────────────────────────────────────────────────────────────

def make_user(**kwargs) -> MagicMock:
    user = MagicMock()
    user.id       = kwargs.get("id", 1)
    user.username = kwargs.get("username", "analyst")
    user.role     = kwargs.get("role", "analyst")
    return user


def make_case(**kwargs) -> MagicMock:
    case = MagicMock()
    case.id          = kwargs.get("id", 1)
    case.case_number = kwargs.get("case_number", "CASE-2024-00001")
    case.title       = kwargs.get("title", "Suspicious wire transfer")
    case.description = kwargs.get("description", "Customer sent $50k to a high-risk country")
    case.status      = kwargs.get("status", "open")
    case.priority    = kwargs.get("priority", "medium")
    case.assigned_to = kwargs.get("assigned_to", None)
    case.created_by  = kwargs.get("created_by", 1)
    case.closed_at   = kwargs.get("closed_at", None)
    case.sar_filed   = kwargs.get("sar_filed", False)
    return case


def make_create_data(**kwargs) -> MagicMock:
    data = MagicMock()
    data.alert_id    = kwargs.get("alert_id", None)
    data.title       = kwargs.get("title", "Suspicious wire transfer")
    data.description = kwargs.get("description", "Details here")
    data.priority    = kwargs.get("priority", "medium")
    data.assigned_to = kwargs.get("assigned_to", None)
    return data


def make_update_data(**kwargs) -> MagicMock:
    data = MagicMock()
    data.status      = kwargs.get("status", None)
    data.priority    = kwargs.get("priority", None)
    data.assigned_to = kwargs.get("assigned_to", None)
    data.resolution  = kwargs.get("resolution", None)
    data.model_dump  = lambda exclude_none=False: {
        k: v for k, v in {
            "status":      data.status,
            "priority":    data.priority,
            "assigned_to": data.assigned_to,
            "resolution":  data.resolution,
        }.items() if not exclude_none or v is not None
    }
    return data


def make_note_data(**kwargs) -> MagicMock:
    data = MagicMock()
    data.note      = kwargs.get("note", "Reviewed transaction history — pattern confirmed")
    data.note_type = kwargs.get("note_type", "comment")
    return data


# ── _generate_case_number ──────────────────────────────────────────────────

class TestGenerateCaseNumber:
    def test_format_starts_with_case(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        number = _generate_case_number(db)
        assert number.startswith("CASE-")

    def test_format_has_three_parts(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        number = _generate_case_number(db)
        parts = number.split("-")
        assert len(parts) == 3

    def test_sequential_numbering(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 4
        number = _generate_case_number(db)
        assert number.endswith("00005")

    def test_year_in_number(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        number = _generate_case_number(db)
        year = str(datetime.now().year)
        assert year in number


# ── create_case() ─────────────────────────────────────────────────────────

class TestCreateCase:
    def _make_db(self, alert=None):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        db.query.return_value.filter.return_value.first.return_value = alert
        db.refresh.side_effect = lambda obj: None
        return db

    def test_creates_case_and_adds_to_db(self, service):
        db = self._make_db()
        data = make_create_data()
        user = make_user()

        with patch("services.case_service.audit_service"):
            result = service.create_case(data, db, user)

        assert db.add.called

    def test_commits_twice_for_case_and_note(self, service):
        db = self._make_db()
        data = make_create_data()
        user = make_user()

        with patch("services.case_service.audit_service"):
            service.create_case(data, db, user)

        assert db.commit.call_count >= 2

    def test_sets_created_by_to_user_id(self, service):
        db = self._make_db()
        data = make_create_data()
        user = make_user(id=5)

        with patch("services.case_service.audit_service"):
            service.create_case(data, db, user)

        added_case = db.add.call_args_list[0][0][0]
        assert added_case.created_by == 5

    def test_raises_404_when_linked_alert_not_found(self, service):
        db = self._make_db(alert=None)
        data = make_create_data(alert_id=999)
        user = make_user()

        with pytest.raises(HTTPException) as exc:
            service.create_case(data, db, user)

        assert exc.value.status_code == 404

    def test_sets_alert_status_to_under_review_when_linked(self, service):
        alert = MagicMock()
        alert.id     = 1
        alert.status = "open"
        db = self._make_db(alert=alert)
        data = make_create_data(alert_id=1)
        user = make_user()

        with patch("services.case_service.audit_service"):
            service.create_case(data, db, user)

        assert alert.status == "under_review"

    def test_no_alert_id_creates_manual_note(self, service):
        db = self._make_db()
        data = make_create_data(alert_id=None)
        user = make_user()

        with patch("services.case_service.audit_service"):
            service.create_case(data, db, user)

        # Second add() call is the CaseNote; check its note text
        note_obj = db.add.call_args_list[1][0][0]
        assert "manually" in note_obj.note.lower()


# ── get_case() ────────────────────────────────────────────────────────────

class TestGetCase:
    def test_returns_case_when_found(self, service):
        case = make_case()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = case
        assert service.get_case(1, db) is case

    def test_raises_404_when_not_found(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.get_case(999, db)
        assert exc.value.status_code == 404


# ── add_note() ────────────────────────────────────────────────────────────

class TestAddNote:
    def test_adds_note_to_db(self, service):
        case = make_case()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = case
        db.refresh.side_effect = lambda obj: None
        note_data = make_note_data()
        user = make_user()

        with patch("services.case_service.audit_service"):
            service.add_note(case.id, note_data, db, user)

        db.add.assert_called_once()

    def test_note_has_correct_case_id(self, service):
        case = make_case(id=7)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = case
        db.refresh.side_effect = lambda obj: None
        note_data = make_note_data(note="PEP match confirmed")
        user = make_user()

        with patch("services.case_service.audit_service"):
            service.add_note(7, note_data, db, user)

        added_note = db.add.call_args[0][0]
        assert added_note.case_id == 7

    def test_note_has_correct_text(self, service):
        case = make_case()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = case
        db.refresh.side_effect = lambda obj: None
        note_data = make_note_data(note="Escalating to supervisor")
        user = make_user()

        with patch("services.case_service.audit_service"):
            service.add_note(case.id, note_data, db, user)

        added_note = db.add.call_args[0][0]
        assert added_note.note == "Escalating to supervisor"

    def test_raises_404_for_missing_case(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.add_note(999, make_note_data(), db, make_user())
        assert exc.value.status_code == 404


# ── update_case() / close_case() ──────────────────────────────────────────

class TestUpdateStatus:
    def _make_db(self, case):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = case
        db.refresh.side_effect = lambda obj: None
        return db

    def test_updates_status_field(self, service):
        case = make_case(status="open")
        db = self._make_db(case)
        data = make_update_data(status="investigating")
        user = make_user(role="supervisor")

        with patch("services.case_service.audit_service"):
            service.update_case(case.id, data, db, user)

        assert case.status == "investigating"

    def test_sets_closed_at_when_closed(self, service):
        case = make_case(status="open")
        db = self._make_db(case)
        data = make_update_data(status="closed")
        user = make_user(role="supervisor")

        with patch("services.case_service.audit_service"):
            service.update_case(case.id, data, db, user)

        assert case.closed_at is not None

    def test_sets_closed_at_when_filed_sar(self, service):
        case = make_case(status="open")
        db = self._make_db(case)
        data = make_update_data(status="filed_sar")
        user = make_user(role="supervisor")

        with patch("services.case_service.audit_service"):
            service.update_case(case.id, data, db, user)

        assert case.closed_at is not None

    def test_analyst_cannot_escalate(self, service):
        case = make_case(status="open")
        db = self._make_db(case)
        data = make_update_data(status="escalated")
        user = make_user(role="analyst")

        with pytest.raises(HTTPException) as exc:
            service.update_case(case.id, data, db, user)

        assert exc.value.status_code == 403

    def test_supervisor_can_escalate(self, service):
        case = make_case(status="open")
        db = self._make_db(case)
        data = make_update_data(status="escalated")
        user = make_user(role="supervisor")

        with patch("services.case_service.audit_service"):
            service.update_case(case.id, data, db, user)

        assert case.status == "escalated"

    def test_status_change_creates_note(self, service):
        case = make_case(status="open")
        db = self._make_db(case)
        data = make_update_data(status="investigating")
        user = make_user(role="supervisor")

        with patch("services.case_service.audit_service"):
            service.update_case(case.id, data, db, user)

        # A CaseNote should have been added (status change note)
        db.add.assert_called()

    def test_raises_404_when_case_missing(self, service):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as exc:
            service.update_case(999, make_update_data(status="closed"), db, make_user())
        assert exc.value.status_code == 404
