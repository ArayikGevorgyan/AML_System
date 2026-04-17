"""
Tests for /cases Router
========================
FastAPI TestClient integration tests covering all case management endpoints:
  - POST /cases               create case
  - GET  /cases               list with status/assigned_to filters
  - GET  /cases/{id}          get case
  - PUT  /cases/{id}          update case status
  - POST /cases/{id}/notes    add note
  - GET  /cases/{id}/notes    list notes
  - Business rule: closed cases cannot be reopened

All DB and auth dependencies are mocked.

Run with:
    pytest backend/tests/test_cases_router.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_case(**kwargs) -> MagicMock:
    """Return a mock Case ORM object with sensible defaults."""
    c = MagicMock()
    c.id = kwargs.get("id", 1)
    c.case_number = kwargs.get("case_number", "CASE-2024-00001")
    c.alert_id = kwargs.get("alert_id", None)
    c.title = kwargs.get("title", "Suspicious wire transfer")
    c.description = kwargs.get("description", "Customer sent funds to high-risk jurisdiction")
    c.status = kwargs.get("status", "open")
    c.priority = kwargs.get("priority", "medium")
    c.assigned_to = kwargs.get("assigned_to", None)
    c.created_by = kwargs.get("created_by", 1)
    c.created_at = kwargs.get("created_at", datetime(2024, 2, 1, 9, 0, tzinfo=timezone.utc))
    c.updated_at = kwargs.get("updated_at", None)
    c.closed_at = kwargs.get("closed_at", None)
    c.resolution = kwargs.get("resolution", None)
    c.sar_filed = kwargs.get("sar_filed", False)
    c.sar_reference = kwargs.get("sar_reference", None)
    return c


def _make_note(**kwargs) -> MagicMock:
    n = MagicMock()
    n.id = kwargs.get("id", 1)
    n.case_id = kwargs.get("case_id", 1)
    n.user_id = kwargs.get("user_id", 1)
    n.note = kwargs.get("note", "Initial investigation started.")
    n.note_type = kwargs.get("note_type", "comment")
    n.created_at = kwargs.get("created_at", datetime(2024, 2, 1, 10, 0, tzinfo=timezone.utc))
    return n


def _make_user(**kwargs) -> MagicMock:
    u = MagicMock()
    u.id = kwargs.get("id", 1)
    u.username = "supervisor1"
    u.role = "supervisor"
    u.is_active = True
    return u


def _paginated(items, total=None, page=1, page_size=50):
    return {"total": total or len(items), "page": page, "page_size": page_size, "items": items}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_user():
    return _make_user()


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer supervisor-token-xyz"}


@pytest.fixture
def app(mock_db, mock_user):
    from fastapi import FastAPI
    from routers.cases import router
    from core.dependencies import get_current_user
    from database import get_db

    _app = FastAPI()
    _app.include_router(router)
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[get_current_user] = lambda: mock_user
    return _app


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /cases — Create Case
# ---------------------------------------------------------------------------

class TestCreateCase:
    """Tests for case creation."""

    def test_create_case_minimal(self, client, auth_headers):
        """Create a case with only a title succeeds."""
        case = _make_case(id=1, title="Manual review case")

        with patch("services.case_service.case_service.create_case", return_value=case):
            resp = client.post(
                "/cases",
                json={"title": "Manual review case"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["title"] == "Manual review case"

    def test_create_case_from_alert(self, client, auth_headers):
        """Case linked to an alert_id stores the relationship."""
        case = _make_case(id=2, alert_id=42, title="Alert escalation")

        with patch("services.case_service.case_service.create_case", return_value=case):
            resp = client.post(
                "/cases",
                json={"title": "Alert escalation", "alert_id": 42, "priority": "high"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["alert_id"] == 42

    def test_create_case_with_priority(self, client, auth_headers):
        """Case priority is stored correctly."""
        case = _make_case(id=3, priority="critical", title="Critical SAR review")

        with patch("services.case_service.case_service.create_case", return_value=case):
            resp = client.post(
                "/cases",
                json={"title": "Critical SAR review", "priority": "critical"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["priority"] == "critical"

    def test_create_case_missing_title_returns_422(self, client, auth_headers):
        """Missing title field returns validation error."""
        resp = client.post("/cases", json={"priority": "low"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_create_case_with_assignment(self, client, auth_headers):
        """Case can be created with initial assignment."""
        case = _make_case(id=4, assigned_to=5)

        with patch("services.case_service.case_service.create_case", return_value=case):
            resp = client.post(
                "/cases",
                json={"title": "Assigned case", "assigned_to": 5},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["assigned_to"] == 5

    def test_create_case_missing_alert_returns_404(self, client, auth_headers):
        """Referencing a nonexistent alert_id raises 404."""
        from fastapi import HTTPException

        with patch("services.case_service.case_service.create_case",
                   side_effect=HTTPException(status_code=404, detail="Alert not found")):
            resp = client.post(
                "/cases",
                json={"title": "Ghost alert case", "alert_id": 9999},
                headers=auth_headers,
            )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /cases — List Cases
# ---------------------------------------------------------------------------

class TestListCases:
    """Tests for case listing with filters."""

    def test_list_all_cases(self, client, auth_headers):
        """Default list returns all cases paginated."""
        cases = [_make_case(id=i) for i in range(4)]

        with patch("services.case_service.case_service.list_cases",
                   return_value=_paginated(cases)):
            resp = client.get("/cases", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["total"] == 4

    def test_filter_by_status_open(self, client, auth_headers):
        """Filtering by status=open returns only open cases."""
        open_cases = [_make_case(id=i, status="open") for i in range(2)]

        with patch("services.case_service.case_service.list_cases",
                   return_value=_paginated(open_cases)):
            resp = client.get("/cases?status=open", headers=auth_headers)

        assert resp.status_code == 200
        for c in resp.json()["items"]:
            assert c["status"] == "open"

    def test_filter_by_status_investigating(self, client, auth_headers):
        """Filtering by status=investigating works correctly."""
        inv_cases = [_make_case(id=10, status="investigating")]

        with patch("services.case_service.case_service.list_cases",
                   return_value=_paginated(inv_cases)):
            resp = client.get("/cases?status=investigating", headers=auth_headers)

        assert resp.status_code == 200

    def test_filter_by_assigned_to(self, client, auth_headers):
        """assigned_to filter scopes cases to an analyst."""
        assigned = [_make_case(id=20, assigned_to=3)]

        with patch("services.case_service.case_service.list_cases",
                   return_value=_paginated(assigned)):
            resp = client.get("/cases?assigned_to=3", headers=auth_headers)

        assert resp.status_code == 200

    def test_empty_list(self, client, auth_headers):
        """No matching cases returns total=0."""
        with patch("services.case_service.case_service.list_cases",
                   return_value=_paginated([])):
            resp = client.get("/cases?status=closed", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# GET /cases/{id} — Get Case
# ---------------------------------------------------------------------------

class TestGetCase:
    """Tests for single case retrieval."""

    def test_returns_case_when_found(self, client, auth_headers):
        """Existing case is returned with all fields."""
        case = _make_case(id=7, title="Wire fraud investigation")

        with patch("services.case_service.case_service.get_case", return_value=case):
            resp = client.get("/cases/7", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["id"] == 7
        assert resp.json()["title"] == "Wire fraud investigation"

    def test_returns_404_for_missing_case(self, client, auth_headers):
        """Non-existent case ID returns 404."""
        from fastapi import HTTPException

        with patch("services.case_service.case_service.get_case",
                   side_effect=HTTPException(status_code=404, detail="Case not found")):
            resp = client.get("/cases/9999", headers=auth_headers)

        assert resp.status_code == 404

    def test_case_sar_fields_present(self, client, auth_headers):
        """Case includes sar_filed and sar_reference fields."""
        case = _make_case(id=8, sar_filed=True, sar_reference="SAR-2024-00001")

        with patch("services.case_service.case_service.get_case", return_value=case):
            resp = client.get("/cases/8", headers=auth_headers)

        assert resp.json()["sar_filed"] is True
        assert resp.json()["sar_reference"] == "SAR-2024-00001"


# ---------------------------------------------------------------------------
# PUT /cases/{id} — Update Case Status
# ---------------------------------------------------------------------------

class TestUpdateCase:
    """Tests for case status transitions."""

    def test_move_to_investigating(self, client, auth_headers):
        """Open case can be moved to investigating."""
        updated = _make_case(id=1, status="investigating")

        with patch("services.case_service.case_service.update_case", return_value=updated):
            resp = client.put(
                "/cases/1",
                json={"status": "investigating"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "investigating"

    def test_assign_case_to_analyst(self, client, auth_headers):
        """Case can be assigned to a user."""
        assigned = _make_case(id=2, assigned_to=7)

        with patch("services.case_service.case_service.update_case", return_value=assigned):
            resp = client.put(
                "/cases/2",
                json={"assigned_to": 7},
                headers=auth_headers,
            )

        assert resp.json()["assigned_to"] == 7

    def test_close_case_with_resolution(self, client, auth_headers):
        """Closing a case with resolution text succeeds."""
        closed = _make_case(
            id=3, status="closed",
            closed_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
            resolution="No suspicious activity confirmed.",
        )

        with patch("services.case_service.case_service.update_case", return_value=closed):
            resp = client.put(
                "/cases/3",
                json={"status": "closed", "resolution": "No suspicious activity confirmed."},
                headers=auth_headers,
            )

        assert resp.json()["status"] == "closed"
        assert resp.json()["resolution"] is not None

    def test_close_case_sets_closed_at(self, client, auth_headers):
        """closed_at is set when case is closed."""
        closed = _make_case(
            id=4, status="closed",
            closed_at=datetime(2024, 4, 10, tzinfo=timezone.utc),
        )

        with patch("services.case_service.case_service.update_case", return_value=closed):
            resp = client.put("/cases/4", json={"status": "closed"}, headers=auth_headers)

        assert resp.json()["closed_at"] is not None

    def test_closed_case_cannot_be_reopened(self, client, auth_headers):
        """Attempting to reopen a closed case raises an error."""
        from fastapi import HTTPException

        with patch("services.case_service.case_service.update_case",
                   side_effect=HTTPException(status_code=400,
                                             detail="Cannot reopen a closed case")):
            resp = client.put(
                "/cases/5",
                json={"status": "open"},
                headers=auth_headers,
            )

        assert resp.status_code == 400
        assert "reopen" in resp.json()["detail"].lower() or "closed" in resp.json()["detail"].lower()

    def test_mark_sar_filed(self, client, auth_headers):
        """SAR filed flag can be set on a case."""
        sar_case = _make_case(id=6, sar_filed=True, sar_reference="SAR-2024-00005")

        with patch("services.case_service.case_service.update_case", return_value=sar_case):
            resp = client.put(
                "/cases/6",
                json={"sar_filed": True, "sar_reference": "SAR-2024-00005"},
                headers=auth_headers,
            )

        assert resp.json()["sar_filed"] is True

    def test_update_nonexistent_case_returns_404(self, client, auth_headers):
        """Updating a missing case returns 404."""
        from fastapi import HTTPException

        with patch("services.case_service.case_service.update_case",
                   side_effect=HTTPException(status_code=404, detail="Case not found")):
            resp = client.put("/cases/9999", json={"status": "closed"}, headers=auth_headers)

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /cases/{id}/notes — Add Note
# ---------------------------------------------------------------------------

class TestAddNote:
    """Tests for case note creation."""

    def test_add_comment_note(self, client, auth_headers):
        """Analyst can add a comment to an open case."""
        note = _make_note(id=1, note="Reviewed transaction history. No pattern yet.")

        with patch("services.case_service.case_service.add_note", return_value=note):
            resp = client.post(
                "/cases/1/notes",
                json={"note": "Reviewed transaction history. No pattern yet.", "note_type": "comment"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert "Reviewed" in resp.json()["note"]

    def test_add_status_change_note(self, client, auth_headers):
        """Status-change notes are stored with correct note_type."""
        note = _make_note(id=2, note="Case escalated to supervisor.", note_type="status_change")

        with patch("services.case_service.case_service.add_note", return_value=note):
            resp = client.post(
                "/cases/1/notes",
                json={"note": "Case escalated to supervisor.", "note_type": "status_change"},
                headers=auth_headers,
            )

        assert resp.json()["note_type"] == "status_change"

    def test_add_note_missing_text_returns_422(self, client, auth_headers):
        """Missing note text returns 422."""
        resp = client.post("/cases/1/notes", json={"note_type": "comment"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_add_note_to_nonexistent_case_returns_404(self, client, auth_headers):
        """Adding note to missing case returns 404."""
        from fastapi import HTTPException

        with patch("services.case_service.case_service.add_note",
                   side_effect=HTTPException(status_code=404, detail="Case not found")):
            resp = client.post(
                "/cases/9999/notes",
                json={"note": "Test note"},
                headers=auth_headers,
            )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /cases/{id}/notes — List Notes
# ---------------------------------------------------------------------------

class TestGetNotes:
    """Tests for retrieving case notes."""

    def test_returns_all_notes(self, client, auth_headers):
        """All notes for a case are returned in a list."""
        notes = [
            _make_note(id=1, note="Initial review."),
            _make_note(id=2, note="Requested KYC docs."),
            _make_note(id=3, note="Docs received."),
        ]

        with patch("services.case_service.case_service.get_notes", return_value=notes):
            resp = client.get("/cases/1/notes", headers=auth_headers)

        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_returns_empty_list_for_no_notes(self, client, auth_headers):
        """Case with no notes returns empty list."""
        with patch("services.case_service.case_service.get_notes", return_value=[]):
            resp = client.get("/cases/2/notes", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json() == []

    def test_note_fields_present(self, client, auth_headers):
        """Each note includes required fields."""
        note = _make_note(id=5, case_id=3, note="Important finding.")

        with patch("services.case_service.case_service.get_notes", return_value=[note]):
            resp = client.get("/cases/3/notes", headers=auth_headers)

        assert resp.status_code == 200
        n = resp.json()[0]
        assert "note" in n
        assert "note_type" in n
        assert "created_at" in n
