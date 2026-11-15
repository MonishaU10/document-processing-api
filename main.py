
import os
import shutil
from uuid import uuid4

import pymupdf
from docx import Document as WordDocument
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from models import Document as DocumentModel
from schemas import DocumentUpdate




app = FastAPI(title="Document Processing API")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MiB


@app.get("/")
def home():
    return {"message": "Hello from my VS Code project!"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is missing",
        )

    # Validate the file extension.
    allowed_extensions = {".pdf", ".txt", ".docx"}
    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, TXT, and DOCX files are allowed",
        )

    file_size = 0
    file_path = None
    file_created = False

    try:
        # Check file size in chunks.
        while True:
            chunk = await file.read(1024 * 1024)

            if not chunk:
                break

            file_size += len(chunk)

            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="File size must not exceed 5 MB",
                )

        await file.seek(0)

        # Preserve the original filename for display.
        safe_filename = os.path.basename(file.filename)

        # Generate a unique physical storage filename.
        stored_filename = f"{uuid4().hex}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, stored_filename)

        # Create a new file without overwriting an existing file.
        try:
            with open(file_path, "xb") as buffer:
                file_created = True
                shutil.copyfileobj(file.file, buffer)

        except FileExistsError:
            raise HTTPException(
                status_code=409,
                detail="Could not allocate a unique storage filename",
            )

        # Extract text from the document.
        try:
            page_count = None

            if file_extension == ".pdf":
                with open(file_path, "rb") as pdf_file:
                    pdf_bytes=pdf_file.read();
                with pymupdf.open(
                    stream=pdf_bytes,
                    filetype="pdf"
                )as pdf:
                    page_count=len(pdf);
                    extracted_text="\n".join(
                        page.get_text() for page in pdf 
                    )

            elif file_extension == ".txt":
                with open(
                    file_path,
                    "r",
                    encoding="utf-8-sig",
                ) as document:
                    extracted_text = document.read()

            else:  # DOCX
                word_document = WordDocument(file_path)
                extracted_text = "\n".join(
                    paragraph.text
                    for paragraph in word_document.paragraphs
                )

        except Exception as error:
            print("Document extraction error:", repr(error))

            if file_created and os.path.exists(file_path):
                try:
                     os.remove(file_path)
                except OSError as cleanup_error:

                    print("File cleanup error:", repr(cleanup_error))


            raise HTTPException(
                status_code=400,
                detail=(
                    "The document could not be read. "
                    "Check that its format and contents are valid."
                ),
            )

        # Calculate document statistics.
        word_count = len(extracted_text.split())
        character_count = len(extracted_text)

        # Create the database record.
        document_record = DocumentModel(
            filename=safe_filename,
            stored_filename=stored_filename,
            file_type=file_extension,
            size_bytes=file_size,
            word_count=word_count,
            character_count=character_count,
            page_count=page_count,
        )

        # Save metadata to PostgreSQL.
        try:
            db.add(document_record)
            db.commit()
            db.refresh(document_record)

        except Exception as error:
            db.rollback()
            print("Database save error:", repr(error))

            if file_created and file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path);
                except OSError as cleanup_error:
                     print("File cleanup error:", repr(cleanup_error))

            raise HTTPException(
                status_code=500,
                detail="Could not save document metadata to the database",
            )

        return {
            "id": document_record.id,
            "filename": document_record.filename,
            "file_type": document_record.file_type,
            "size_bytes": document_record.size_bytes,
            "page_count": document_record.page_count,
            "word_count": document_record.word_count,
            "character_count": document_record.character_count,
            "extracted_text": extracted_text,
            "message": "Document uploaded, processed, and saved successfully",
        }

    except HTTPException:
        raise

    except OSError as error:
        print("File operation error:", repr(error))

        if file_created and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as cleanup_error:
                print("File cleanup error:", repr(cleanup_error))

        raise HTTPException(
            status_code=500,
            detail="Could not save or process the document",
        )

    except Exception as error:
        print("Unexpected upload error:", repr(error))

        if file_created and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as cleanup_error:
                print("File cleanup error:", repr(cleanup_error))

        raise HTTPException(
            status_code=500,
            detail="Unexpected error while processing the document",
        )

    finally:
        await file.close()


@app.get("/documents")
def get_documents(db: Session = Depends(get_db)):
    documents = db.query(DocumentModel).all()

    return [
        {
            "id": document.id,
            "filename": document.filename,
            "file_type": document.file_type,
            "size_bytes": document.size_bytes,
            "word_count": document.word_count,
            "character_count": document.character_count,
            "page_count": document.page_count,
        }
        for document in documents
    ]


@app.get("/documents/{document_id}")
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    document = (
        db.query(DocumentModel)
        .filter(DocumentModel.id == document_id)
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return {
        "id": document.id,
        "filename": document.filename,
        "file_type": document.file_type,
        "size_bytes": document.size_bytes,
        "word_count": document.word_count,
        "character_count": document.character_count,
        "page_count": document.page_count,
    }


@app.patch("/documents/{document_id}")
def update_document(
    document_id: int,
    updates: DocumentUpdate,
    db: Session = Depends(get_db),
):
    document = (
        db.query(DocumentModel)
        .filter(DocumentModel.id == document_id)
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    update_data = updates.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update",
        )

    if "filename" in update_data:
        new_filename = update_data["filename"]

        if new_filename is None or not new_filename.strip():
            raise HTTPException(
                status_code=422,
                detail="Filename cannot be empty",
            )

        new_filename = new_filename.strip()

        if os.path.basename(new_filename) != new_filename:
            raise HTTPException(
                status_code=422,
                detail="Filename must not contain directory paths",
            )

        # Ensure the new filename keeps the original file type.
        new_extension = os.path.splitext(new_filename)[1].lower()

        if new_extension != document.file_type:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Filename extension must remain "
                    f"{document.file_type}"
                ),
            )

        # Change the display filename only.
        # The physical file keeps its unique stored_filename.
        document.filename = new_filename

    try:
        db.commit()
        db.refresh(document)

    except Exception as error:
        db.rollback()
        print("Database update error:", repr(error))

        raise HTTPException(
            status_code=500,
            detail="Could not update document",
        )

    return {
        "message": "Document updated successfully",
        "id": document.id,
        "filename": document.filename,
    }


@app.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    # Find the database record.
    document = (
        db.query(DocumentModel)
        .filter(DocumentModel.id == document_id)
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    # Save the internal filename before deleting the record.
    stored_filename = document.stored_filename

    # Delete the database record first.
    try:
        db.delete(document)
        db.commit()

    except Exception as error:
        db.rollback()
        print("Database deletion error:", repr(error))

        raise HTTPException(
            status_code=500,
            detail="Could not delete document record",
        )

    file_cleanup_status = "not_needed"

    # Remove the physical file if no records still reference it.
    try:
        remaining_document = (
            db.query(DocumentModel.id)
            .filter(
                DocumentModel.stored_filename == stored_filename
            )
            .first()
        )

        if remaining_document is not None:
            file_cleanup_status = "retained_shared_file"

        elif stored_filename:
            safe_stored_filename = os.path.basename(stored_filename)
            file_path = os.path.join(
                UPLOAD_DIR,
                safe_stored_filename,
            )

            if os.path.exists(file_path):
                os.remove(file_path)
                file_cleanup_status = "removed"
            else:
                file_cleanup_status = "file_not_found"

    except Exception as error:
        print("File cleanup error:", repr(error))
        file_cleanup_status = "failed"

    return {
        "message": "Document record deleted successfully",
        "id": document_id,
        "file_cleanup_status": file_cleanup_status,
    }
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

    # The API should report the database error.
    assert response.status_code == 500

    # No new physical file should remain.
    files_after = set(os.listdir("uploads"))
    assert files_after == files_before