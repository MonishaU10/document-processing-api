
import os
from uuid import uuid4

from fastapi.testclient import TestClient
from database import SessionLocal
from models import Document as DocumentModel
from main import app
import io
import pymupdf
from docx import Document as WordDocument
from sqlalchemy.orm import Session


client = TestClient(app)


def cleanup_test_document(document_id):
    """Remove a test document's database record and stored file."""
    if document_id is None:
        return

    db = SessionLocal()

    try:
        document = (
            db.query(DocumentModel)
            .filter(DocumentModel.id == document_id)
            .first()
        )

        stored_filename = (
            document.stored_filename if document else None
        )

    finally:
        db.close()

    # Delete the database record
    client.delete(f"/documents/{document_id}")

    # Delete the physical file using its internal storage name
    if stored_filename:
        file_path = os.path.join("uploads", stored_filename)

        if os.path.exists(file_path):
            os.remove(file_path)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_txt():
    filename = f"sample-{uuid4().hex}.txt"
    document_id = None

    try:
        response = client.post(
            "/upload",
            files={
                "file": (
                    filename,
                    b"Hello world.\nThis is my first API test.\n",
                    "text/plain"
                )
            }
        )

        if response.status_code == 200:
            document_id = response.json().get("id")

        assert response.status_code == 200

        data = response.json()

        assert data["filename"] == filename
        assert data["file_type"] == ".txt"
        assert data["word_count"] == 8

    finally:
        cleanup_test_document(document_id)


def test_upload_unsupported_file():
    response = client.post(
        "/upload",
        files={
            "file": (
                "sample.jpg",
                b"fake image content",
                "image/jpeg"
            )
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Only PDF, TXT, and DOCX files are allowed"
    )


def test_upload_oversized_file():
    oversized_content = b"a" * (5 * 1024 * 1024 + 1)

    response = client.post(
        "/upload",
        files={
            "file": (
                "large.txt",
                oversized_content,
                "text/plain"
            )
        }
    )

    assert response.status_code == 413
    assert response.json()["detail"] == (
        "File size must not exceed 5 MB"
    )


def test_duplicate_filename():
    filename = f"duplicate-{uuid4().hex}.txt"
    document_ids = []

    try:
        # First upload
        first_response = client.post(
            "/upload",
            files={
                "file": (
                    filename,
                    b"First document",
                    "text/plain"
                )
            }
        )

        if first_response.status_code == 200:
            document_ids.append(first_response.json()["id"])

        assert first_response.status_code == 200

        # Second upload uses the same original filename
        second_response = client.post(
            "/upload",
            files={
                "file": (
                    filename,
                    b"Second document",
                    "text/plain"
                )
            }
        )

        if second_response.status_code == 200:
            document_ids.append(second_response.json()["id"])

        assert second_response.status_code == 200

        first_id = first_response.json()["id"]
        second_id = second_response.json()["id"]

        # Both uploads must create different database records
        assert first_id != second_id

        # Confirm that the stored filenames are different
        db = SessionLocal()

        try:
            first_document = (
                db.query(DocumentModel)
                .filter(DocumentModel.id == first_id)
                .first()
            )

            second_document = (
                db.query(DocumentModel)
                .filter(DocumentModel.id == second_id)
                .first()
            )

            assert first_document is not None
            assert second_document is not None

            assert first_document.filename == filename
            assert second_document.filename == filename

            assert (
                first_document.stored_filename
                != second_document.stored_filename
            )

        finally:
            db.close()

    finally:
        for document_id in document_ids:
            cleanup_test_document(document_id)
    
def test_delete_document_removes_file():
    filename = f"delete-{uuid4().hex}.txt"
    document_id = None
    file_path = None

    try:
        # Upload a test document
        upload_response = client.post(
            "/upload",
            files={
                "file": (
                    filename,
                    b"Document to test deletion",
                    "text/plain"
                )
            }
        )

        assert upload_response.status_code == 200
        document_id = upload_response.json()["id"]

        # Find the physical storage filename in PostgreSQL
        db = SessionLocal()

        try:
            document = (
                db.query(DocumentModel)
                .filter(DocumentModel.id == document_id)
                .first()
            )

            assert document is not None

            stored_filename = document.stored_filename

        finally:
            db.close()

        file_path = os.path.join("uploads", stored_filename)
        assert os.path.exists(file_path)

        # Delete the document using the API
        delete_response = client.delete(
            f"/documents/{document_id}"
        )

        assert delete_response.status_code == 200
        assert (
            delete_response.json()["file_cleanup_status"]
            == "removed"
        )

        # Confirm that the physical file was removed
        assert not os.path.exists(file_path)

        # Confirm that the database record no longer exists
        get_response = client.get(
            f"/documents/{document_id}"
        )

        assert get_response.status_code == 404

    finally:
        # Clean up if the test fails partway through
        if document_id is not None:
            get_response = client.get(
                f"/documents/{document_id}"
            )

            if get_response.status_code != 404:
                cleanup_test_document(document_id)

        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    
def test_get_all_documents():
    filename = f"get-all-{uuid4().hex}.txt"
    document_id = None

    try:
        # Create a document to retrieve
        upload_response = client.post(
            "/upload",
            files={
                "file": (
                    filename,
                    b"Document for GET all test",
                    "text/plain"
                )
            }
        )

        assert upload_response.status_code == 200
        document_id = upload_response.json()["id"]

        # Retrieve all document records
        response = client.get("/documents")

        assert response.status_code == 200

        documents = response.json()
        matching_documents = [
            document for document in documents
            if document["id"] == document_id
        ]

        assert len(matching_documents) == 1
        assert matching_documents[0]["filename"] == filename

    finally:
        cleanup_test_document(document_id)


def test_get_document_by_id():
    filename = f"get-one-{uuid4().hex}.txt"
    document_id = None

    try:
        # Upload a document
        upload_response = client.post(
            "/upload",
            files={
                "file": (
                    filename,
                    b"Document for GET by ID test",
                    "text/plain"
                )
            }
        )

        assert upload_response.status_code == 200
        document_id = upload_response.json()["id"]

        # Retrieve that document by its ID
        response = client.get(f"/documents/{document_id}")

        assert response.status_code == 200

        data = response.json()
        assert data["id"] == document_id
        assert data["filename"] == filename
        assert data["file_type"] == ".txt"

    finally:
        cleanup_test_document(document_id)

    
def test_patch_update_filename():
    filename = f"patch-{uuid4().hex}.txt"
    new_filename = f"updated-{uuid4().hex}.txt"
    document_id = None

    try:
        upload_response = client.post(
            "/upload",
            files={
                "file": (
                    filename,
                    b"Document for PATCH test",
                    "text/plain"
                )
            }
        )

        assert upload_response.status_code == 200
        document_id = upload_response.json()["id"]

        response = client.patch(
            f"/documents/{document_id}",
            json={"filename": new_filename}
        )

        assert response.status_code == 200
        assert response.json()["filename"] == new_filename

        # Confirm the updated filename was saved
        get_response = client.get(f"/documents/{document_id}")

        assert get_response.status_code == 200
        assert get_response.json()["filename"] == new_filename

    finally:
        cleanup_test_document(document_id)


def test_patch_rejects_different_extension():
    filename = f"patch-validation-{uuid4().hex}.txt"
    document_id = None

    try:
        upload_response = client.post(
            "/upload",
            files={
                "file": (
                    filename,
                    b"Document for extension validation",
                    "text/plain"
                )
            }
        )

        assert upload_response.status_code == 200
        document_id = upload_response.json()["id"]

        response = client.patch(
            f"/documents/{document_id}",
            json={"filename": "renamed.pdf"}
        )

        assert response.status_code == 422

        # The original filename must remain unchanged
        get_response = client.get(f"/documents/{document_id}")

        assert get_response.status_code == 200
        assert get_response.json()["filename"] == filename

    finally:
        cleanup_test_document(document_id)


def test_get_missing_document():
    response = client.get("/documents/999999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_patch_missing_document():
    response = client.patch(
        "/documents/999999999",
        json={"filename": "missing.txt"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_delete_missing_document():
    response = client.delete("/documents/999999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"

def test_upload_invalid_pdf():
    filename = f"invalid-{uuid4().hex}.pdf"

    response = client.post(
        "/upload",
        files={
            "file": (
                filename,
                b"This is not a real PDF document",
                "application/pdf"
            )
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "The document could not be read. "
        "Check that its format and contents are valid."
    )
def test_upload_invalid_pdf():
    filename = f"invalid-{uuid4().hex}.pdf"

    response = client.post(
        "/upload",
        files={
            "file": (
                filename,
                b"This is not a real PDF document",
                "application/pdf"
            )
        }
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "The document could not be read. "
        "Check that its format and contents are valid."
    )

def test_patch_keeps_physical_file_intact():
    filename = f"consistency-{uuid4().hex}.txt"
    document_id = None
    stored_filename = None

    try:
        # Upload a test document
        upload_response = client.post(
            "/upload",
            files={
                "file": (
                    filename,
                    b"Testing database and file consistency",
                    "text/plain"
                )
            }
        )

        assert upload_response.status_code == 200
        document_id = upload_response.json()["id"]

        # Read its internal storage filename from PostgreSQL
        db = SessionLocal()

        try:
            document = (
                db.query(DocumentModel)
                .filter(DocumentModel.id == document_id)
                .first()
            )

            assert document is not None
            stored_filename = document.stored_filename

        finally:
            db.close()

        file_path = os.path.join("uploads", stored_filename)
        assert os.path.exists(file_path)

        # Change only the display filename
        new_filename = f"renamed-{uuid4().hex}.txt"

        patch_response = client.patch(
            f"/documents/{document_id}",
            json={"filename": new_filename}
        )

        assert patch_response.status_code == 200
        assert patch_response.json()["filename"] == new_filename

        # Verify the database and physical file are still linked
        db = SessionLocal()

        try:
            updated_document = (
                db.query(DocumentModel)
                .filter(DocumentModel.id == document_id)
                .first()
            )

            assert updated_document is not None
            assert updated_document.filename == new_filename
            assert updated_document.stored_filename == stored_filename

        finally:
            db.close()

        assert os.path.exists(file_path)

    finally:
        cleanup_test_document(document_id)
def test_upload_valid_pdf():
    document_id = None

    # Create a valid PDF in memory.
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Valid PDF upload test")
    pdf_bytes = pdf.tobytes()
    pdf.close()

    try:
        response = client.post(
            "/upload",
            files={
                "file": (
                    "valid-test.pdf",
                    pdf_bytes,
                    "application/pdf",
                )
            },
        )

        assert response.status_code == 200

        result = response.json()
        document_id = result["id"]

        assert "Valid PDF upload test" in result["extracted_text"]
        assert result["page_count"] == 1
        assert result["word_count"] >= 4

    finally:
        if document_id is not None:
            cleanup_test_document(document_id)


def test_upload_valid_docx():
    document_id = None

    # Create a valid DOCX in memory.
    word_document = WordDocument()
    word_document.add_paragraph("Valid DOCX upload test")

    docx_buffer = io.BytesIO()
    word_document.save(docx_buffer)
    docx_bytes = docx_buffer.getvalue()

    try:
        response = client.post(
            "/upload",
            files={
                "file": (
                    "valid-test.docx",
                    docx_bytes,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

        assert response.status_code == 200

        result = response.json()
        document_id = result["id"]

        assert "Valid DOCX upload test" in result["extracted_text"]
        assert result["word_count"] >= 4
        assert result["character_count"] > 0

    finally:
        if document_id is not None:
            cleanup_test_document(document_id)

def test_upload_database_failure_cleans_up_file(monkeypatch):
    files_before = set(os.listdir("uploads"))

    # Simulate a database commit failure.
    def fail_commit(self):
        raise RuntimeError("Simulated database failure")

    monkeypatch.setattr(Session, "commit", fail_commit)

    response = client.post(
        "/upload",
        files={
            "file": (
                f"db-failure-{uuid4().hex}.txt",
                b"Testing database failure cleanup",
                "text/plain",
            )
        },
    )

    assert response.status_code == 500

    # Confirm the uploaded file was removed.
    files_after = set(os.listdir("uploads"))
    assert files_after == files_before