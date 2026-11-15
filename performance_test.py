
import io
import statistics
import time

import httpx
import pymupdf
from docx import Document as WordDocument


BASE_URL = "http://127.0.0.1:8000"
REPETITIONS = 3


def create_txt():
    content = (
        "Performance testing line: document text extraction benchmark.\n"
        * 500
    )
    return content.encode("utf-8")


def create_pdf():
    pdf = pymupdf.open()

    text = "\n".join(
        f"Performance testing line {i}: text extraction benchmark."
        for i in range(1, 31)
    )

    for _ in range(3):
        page = pdf.new_page()
        page.insert_textbox(
            pymupdf.Rect(50, 50, 550, 780),
            text,
            fontsize=10,
        )

    pdf_bytes = pdf.tobytes()
    pdf.close()

    return pdf_bytes


def create_docx():
    document = WordDocument()

    for i in range(500):
        document.add_paragraph(
            f"Performance testing line {i}: "
            "document text extraction benchmark."
        )

    buffer = io.BytesIO()
    document.save(buffer)

    return buffer.getvalue()


def main():
    test_files = [
        (
            "TXT",
            "benchmark.txt",
            create_txt(),
            "text/plain",
        ),
        (
            "PDF",
            "benchmark.pdf",
            create_pdf(),
            "application/pdf",
        ),
        (
            "DOCX",
            "benchmark.docx",
            create_docx(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ]

    uploaded_ids = []
    results = []

    with httpx.Client(timeout=60.0) as client:
        # Check whether the API is running.
        try:
            health_response = client.get(f"{BASE_URL}/health")
        except httpx.RequestError:
            print("Could not connect to the API.")
            print("Start the server using:")
            print("python -m uvicorn main:app --reload")
            return

        if health_response.status_code != 200:
            print("API health check failed.")
            return

        print("API is running.")
        print("Starting performance evaluation...\n")

        try:
            for file_type, filename, content, content_type in test_files:
                durations = []
                successes = 0

                print(
                    f"Testing {file_type}: "
                    f"{len(content):,} bytes"
                )

                for run in range(1, REPETITIONS + 1):
                    start_time = time.perf_counter()

                    response = client.post(
                        f"{BASE_URL}/upload",
                        files={
                            "file": (
                                filename,
                                content,
                                content_type,
                            )
                        },
                    )

                    elapsed_ms = (
                        time.perf_counter() - start_time
                    ) * 1000

                    durations.append(elapsed_ms)

                    if response.status_code == 200:
                        successes += 1

                        document_id = response.json().get("id")

                        if document_id is not None:
                            uploaded_ids.append(document_id)

                        print(
                            f"  Run {run}: "
                            f"{elapsed_ms:.2f} ms - SUCCESS"
                        )
                    else:
                        print(
                            f"  Run {run}: "
                            f"{elapsed_ms:.2f} ms - FAILED "
                            f"({response.status_code})"
                        )
                        print(f"  Details: {response.text}")

                results.append({
                    "type": file_type,
                    "size": len(content),
                    "successes": successes,
                    "total": REPETITIONS,
                    "average_ms": statistics.mean(durations),
                    "minimum_ms": min(durations),
                    "maximum_ms": max(durations),
                })

                print()

        finally:
            # Remove only documents created by this benchmark.
            print("Cleaning up benchmark documents...")

            for document_id in uploaded_ids:
                try:
                    cleanup_response = client.delete(
                        f"{BASE_URL}/documents/{document_id}"
                    )

                    if cleanup_response.status_code not in (200, 204):
                        print(
                            f"Cleanup failed for document "
                            f"{document_id}: "
                            f"{cleanup_response.status_code}"
                        )

                except httpx.RequestError as error:
                    print(
                        f"Could not clean up document "
                        f"{document_id}: {error}"
                    )

    print("\n========== PERFORMANCE REPORT ==========")

    print(
        f"{'Format':<10}"
        f"{'Size (bytes)':>14}"
        f"{'Success rate':>16}"
        f"{'Average (ms)':>16}"
        f"{'Min (ms)':>12}"
        f"{'Max (ms)':>12}"
    )

    for result in results:
        success_rate = (
            result["successes"] / result["total"]
        ) * 100

        print(
            f"{result['type']:<10}"
            f"{result['size']:>14,}"
            f"{success_rate:>15.1f}%"
            f"{result['average_ms']:>16.2f}"
            f"{result['minimum_ms']:>12.2f}"
            f"{result['maximum_ms']:>12.2f}"
        )

    print("========================================")


if __name__ == "__main__":
    main()
