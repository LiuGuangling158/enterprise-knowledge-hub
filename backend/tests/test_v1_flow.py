import os
import unittest
from pathlib import Path
from uuid import uuid4


TEST_DB = Path(__file__).resolve().parents[1] / "test_knowledge_v1.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from database.session import engine  # noqa: E402
from main import app  # noqa: E402


class V1FlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)
        engine.dispose()
        if TEST_DB.exists():
            TEST_DB.unlink()

    def login(self, email: str) -> dict[str, str]:
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "123456"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_comment_and_document_approval_history_flow(self) -> None:
        headers = self.login("admin@example.com")
        suffix = uuid4().hex[:8]

        created = self.client.post(
            "/api/documents",
            headers=headers,
            json={
                "title": f"V1 flow doc {suffix}",
                "content": "Initial content",
                "tags": ["v1", "flow"],
                "visibility": "public",
                "department_id": "dept-product",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        document_id = created.json()["id"]

        updated = self.client.put(
            f"/api/documents/{document_id}",
            headers=headers,
            json={
                "title": f"V1 flow doc {suffix}",
                "content": "Updated before submit",
                "tags": ["v1", "flow"],
                "visibility": "public",
                "summary": "Update before submit",
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)

        comment = self.client.post(
            f"/api/documents/{document_id}/comments",
            headers=headers,
            json={"content": "Looks ready for review."},
        )
        self.assertEqual(comment.status_code, 200, comment.text)
        self.assertEqual(comment.json()["content"], "Looks ready for review.")

        comments = self.client.get(f"/api/documents/{document_id}/comments", headers=headers)
        self.assertEqual(comments.status_code, 200, comments.text)
        self.assertEqual(len(comments.json()), 1)

        submitted = self.client.post(
            f"/api/documents/{document_id}/submit",
            headers=headers,
            json={"summary": "Submit for V1 approval"},
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        approval_id = submitted.json()["id"]

        history = self.client.get(f"/api/documents/{document_id}/approvals", headers=headers)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()[0]["id"], approval_id)
        self.assertEqual(history.json()[0]["status"], "pending")

        reviewed = self.client.post(
            f"/api/approvals/{approval_id}/review",
            headers=headers,
            json={"action": "approve", "reason": "Approved in V1 flow test"},
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        self.assertEqual(reviewed.json()["status"], "approved")

        document = self.client.get(f"/api/documents/{document_id}", headers=headers)
        self.assertEqual(document.status_code, 200, document.text)
        self.assertEqual(document.json()["content"], "Updated before submit")
        self.assertEqual(document.json()["status"], "published")

    def test_non_admin_cannot_write_other_department_document(self) -> None:
        headers = self.login("product@example.com")
        response = self.client.post(
            "/api/documents",
            headers=headers,
            json={
                "title": "Cross department write",
                "content": "Should be blocked",
                "tags": [],
                "visibility": "department",
                "department_id": "dept-tech",
            },
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_invalid_visibility_is_rejected(self) -> None:
        headers = self.login("admin@example.com")
        response = self.client.post(
            "/api/documents",
            headers=headers,
            json={
                "title": "Invalid visibility",
                "content": "Should be rejected",
                "tags": [],
                "visibility": "tenant",
            },
        )
        self.assertEqual(response.status_code, 422, response.text)


if __name__ == "__main__":
    unittest.main()
