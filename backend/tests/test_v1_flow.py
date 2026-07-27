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
from sqlalchemy import text  # noqa: E402

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

        duplicate_submit = self.client.post(
            f"/api/documents/{document_id}/submit",
            headers=headers,
            json={"summary": "Duplicate V1 approval"},
        )
        self.assertEqual(duplicate_submit.status_code, 409, duplicate_submit.text)

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

    def test_archive_hides_document_until_restored(self) -> None:
        headers = self.login("admin@example.com")
        suffix = uuid4().hex[:8]
        created = self.client.post(
            "/api/documents",
            headers=headers,
            json={
                "title": f"Archive flow doc {suffix}",
                "content": "Archive content",
                "tags": ["archive"],
                "visibility": "public",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        document_id = created.json()["id"]

        archived = self.client.post(f"/api/documents/{document_id}/archive", headers=headers)
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(archived.json()["status"], "archived")

        comment_archived = self.client.post(
            f"/api/documents/{document_id}/comments",
            headers=headers,
            json={"content": "Should be blocked"},
        )
        self.assertEqual(comment_archived.status_code, 409, comment_archived.text)

        default_documents = self.client.get("/api/documents", headers=headers)
        self.assertEqual(default_documents.status_code, 200, default_documents.text)
        self.assertNotIn(document_id, [item["id"] for item in default_documents.json()])

        archived_documents = self.client.get("/api/documents?status=archived", headers=headers)
        self.assertEqual(archived_documents.status_code, 200, archived_documents.text)
        self.assertIn(document_id, [item["id"] for item in archived_documents.json()])

        edit_archived = self.client.put(
            f"/api/documents/{document_id}",
            headers=headers,
            json={
                "title": "Should not edit archived",
                "content": "Blocked",
                "tags": ["archive"],
                "visibility": "public",
            },
        )
        self.assertEqual(edit_archived.status_code, 409, edit_archived.text)

        restored = self.client.post(f"/api/documents/{document_id}/restore", headers=headers)
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()["status"], "draft")

        restored_documents = self.client.get("/api/documents", headers=headers)
        self.assertEqual(restored_documents.status_code, 200, restored_documents.text)
        self.assertIn(document_id, [item["id"] for item in restored_documents.json()])

    def test_non_author_cannot_archive_visible_document(self) -> None:
        headers = self.login("product@example.com")
        response = self.client.post("/api/documents/doc-002/archive", headers=headers)
        self.assertEqual(response.status_code, 403, response.text)

    def test_pending_approval_unique_index_exists(self) -> None:
        if engine.dialect.name != "sqlite":
            self.skipTest("index inspection is implemented for sqlite smoke tests")

        with engine.connect() as connection:
            rows = connection.execute(text("PRAGMA index_list('approvals')")).mappings().all()

        self.assertIn(
            "ix_approvals_one_pending_per_document",
            [row["name"] for row in rows],
        )

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
