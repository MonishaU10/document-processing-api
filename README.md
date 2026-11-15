# Document Processing and Management API

A backend application developed using Python, FastAPI, PostgreSQL and SQLAlchemy to upload, validate, process and manage PDF, DOCX and TXT documents.
Project Overview
The Document Processing and Management API automates document handling by accepting multiple document formats, extracting their textual content, calculating document statistics and storing document metadata in a PostgreSQL database.

It provides RESTful API endpoints for uploading, retrieving, renaming and deleting documents.

## Features

- Upload PDF, DOCX and TXT files.
- File validation with a maximum size limit of 5 MiB.
- Text extraction using PyMuPDF and python-docx.
- Word count, character count and PDF page count calculation.
- Store document metadata in PostgreSQL.
- CRUD operations for document management.
- Unique filenames to prevent file overwriting.
- Error handling and file cleanup.
- Automated testing and performance benchmarking.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| FastAPI | REST API development |
| PostgreSQL | Database |
| SQLAlchemy | ORM |
| Pydantic | Data validation |
| PyMuPDF | PDF text extraction |
| python-docx | DOCX text extraction |
| Pytest | Automated testing |
| Uvicorn | ASGI server |

## Project Structure

```text
document-processing-api/
│
├── main.py                 # FastAPI application and API endpoints
├── database.py             # Database connection and sessions
├── models.py               # SQLAlchemy database models
├── schemas.py              # Pydantic schemas
├── create_tables.py        # Database table creation
├── test_db.py              # Database connection test
├── test_main.py            # Automated test cases
├── performance_test.py     # Performance benchmarking
├── requirements.txt        # Project dependencies
├── .env.example            # Environment variable template
├── .gitignore              # Git ignore configuration
│
├── uploads/                # Uploaded documents (local)
└── venv/                   # Python virtual environment (local)
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/MonishaU10/document-processing-api.git
cd document-processing-api
```

### 2. Create and activate a virtual environment

**Windows CMD:**

```cmd
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```cmd
python -m pip install -r requirements.txt
```

### 4. Configure PostgreSQL

Create a PostgreSQL database named:

```text
document_processing_db
```

Create your `.env` file by copying the example:

```cmd
copy .env.example .env
```

Add your PostgreSQL connection URL to `.env`:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/document_processing_db
```

Replace the example username and password with your own database credentials. URL-encode special characters in the password when necessary.

**Important:** Never upload your actual `.env` file or database credentials to GitHub.

### 5. Create database tables

```cmd
python create_tables.py
```

### 6. Start the FastAPI server

```cmd
python -m uvicorn main:app --reload
```

Open Swagger UI in your browser:

http://127.0.0.1:8000/docs

Use Swagger to upload documents and test the API endpoints.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Welcome endpoint |
| GET | `/health` | API health check |
| POST | `/upload` | Upload and process documents |
| GET | `/documents` | Retrieve all documents |
| GET | `/documents/{document_id}` | Retrieve one document |
| PATCH | `/documents/{document_id}` | Rename a document |
| DELETE | `/documents/{document_id}` | Delete a document |

## Testing

### Automated testing

Run the test suite:

```cmd
python -m pytest test_main.py -v
```

**Completed result: 18 tests passed.**

Tests cover document uploads, file validation, CRUD operations, duplicate filenames, file consistency and database failure cleanup.

### Performance evaluation

Keep the FastAPI server running in one terminal. Open another activated terminal and execute:

```cmd
python performance_test.py
```

Initial local benchmark results (three attempts per format):

| Format | Average Upload Time |
|---|---:|
| TXT | 29.19 ms |
| PDF | 12.64 ms |
| DOCX | 43.00 ms |

Observed success rate: **100% (9/9 attempts)**.

These are preliminary local measurements, not concurrent-user load-test results.

## Future Enhancements

- OCR support for scanned PDFs.
- JWT authentication and authorization.
- Full-text document search.
- Cloud-based file storage.
- Enhanced file security.

