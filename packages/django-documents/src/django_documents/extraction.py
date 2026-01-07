"""
Text extraction service for documents.

Extracts text content from various file types:
- PDFs: Using PyPDF2 or pdfplumber
- Images: Using OCR (pytesseract + Tesseract)
- Text files: Direct read

This module provides the foundation for full-text search and AI processing.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of a text extraction operation."""

    success: bool
    text: str = ""
    method: str = ""
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    error: str = ""
    processing_time_ms: int = 0


# Content types that can be processed
EXTRACTABLE_CONTENT_TYPES = {
    # PDFs
    "application/pdf",
    # Images (for OCR)
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "image/bmp",
    "image/gif",
    # Text files
    "text/plain",
    "text/csv",
    "text/html",
    "text/xml",
    "application/json",
    "application/xml",
}


def can_extract(content_type: str) -> bool:
    """Check if text can be extracted from this content type."""
    return content_type.lower() in EXTRACTABLE_CONTENT_TYPES


def extract_text_from_pdf(file_path: str) -> ExtractionResult:
    """
    Extract text from a PDF file.

    Tries PyPDF2 first (fast, text-based PDFs), then pdfplumber
    for more complex layouts.
    """
    start_time = time.time()
    text_parts = []
    page_count = 0

    # Try PyPDF2 first (faster for text-based PDFs)
    try:
        import PyPDF2

        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            page_count = len(reader.pages)

            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        extracted_text = "\n\n".join(text_parts)

        # If we got meaningful text, return it
        if extracted_text.strip():
            processing_time = int((time.time() - start_time) * 1000)
            return ExtractionResult(
                success=True,
                text=extracted_text,
                method="pypdf2",
                page_count=page_count,
                word_count=len(extracted_text.split()),
                processing_time_ms=processing_time,
            )

    except ImportError:
        logger.warning("PyPDF2 not installed, trying pdfplumber")
    except Exception as e:
        logger.warning(f"PyPDF2 extraction failed: {e}")

    # Fall back to pdfplumber for complex layouts
    try:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        extracted_text = "\n\n".join(text_parts)
        processing_time = int((time.time() - start_time) * 1000)

        if extracted_text.strip():
            return ExtractionResult(
                success=True,
                text=extracted_text,
                method="pdfplumber",
                page_count=page_count,
                word_count=len(extracted_text.split()),
                processing_time_ms=processing_time,
            )

    except ImportError:
        logger.warning("pdfplumber not installed")
    except Exception as e:
        logger.warning(f"pdfplumber extraction failed: {e}")

    # No text extracted - try OCR for scanned PDFs
    try:
        from pdf2image import convert_from_path
        import pytesseract

        logger.info(f"No text in PDF, attempting OCR on {page_count} pages...")

        # Convert PDF pages to images
        images = convert_from_path(file_path, dpi=300)
        page_count = len(images)

        text_parts = []
        for i, image in enumerate(images):
            # Convert to RGB if necessary
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")

            # Run OCR on each page
            page_text = pytesseract.image_to_string(image)
            if page_text.strip():
                text_parts.append(page_text.strip())

        extracted_text = "\n\n".join(text_parts)
        processing_time = int((time.time() - start_time) * 1000)

        if extracted_text.strip():
            return ExtractionResult(
                success=True,
                text=extracted_text,
                method="pdf_ocr",
                page_count=page_count,
                word_count=len(extracted_text.split()),
                processing_time_ms=processing_time,
            )

    except ImportError as e:
        logger.warning(f"OCR dependencies not available: {e}")
    except Exception as e:
        logger.warning(f"PDF OCR failed: {e}")

    # All extraction methods failed
    processing_time = int((time.time() - start_time) * 1000)
    return ExtractionResult(
        success=False,
        text="",
        method="pdf_no_text",
        page_count=page_count,
        error="No extractable text found in PDF. OCR failed or produced no text.",
        processing_time_ms=processing_time,
    )


def extract_text_from_image(file_path: str) -> ExtractionResult:
    """
    Extract text from an image using OCR (Tesseract).

    Requires: pytesseract and Tesseract OCR installed on the system.
    """
    start_time = time.time()

    try:
        import pytesseract
        from PIL import Image

        # Open and process image
        with Image.open(file_path) as img:
            # Convert to RGB if necessary (for PNG with transparency, etc.)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Perform OCR
            extracted_text = pytesseract.image_to_string(img)

        processing_time = int((time.time() - start_time) * 1000)

        if extracted_text.strip():
            return ExtractionResult(
                success=True,
                text=extracted_text.strip(),
                method="ocr_tesseract",
                page_count=1,
                word_count=len(extracted_text.split()),
                processing_time_ms=processing_time,
            )
        else:
            return ExtractionResult(
                success=True,
                text="",
                method="ocr_tesseract",
                page_count=1,
                word_count=0,
                processing_time_ms=processing_time,
            )

    except ImportError:
        return ExtractionResult(
            success=False,
            method="ocr_unavailable",
            error="pytesseract not installed. Install with: pip install pytesseract",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )
    except Exception as e:
        return ExtractionResult(
            success=False,
            method="ocr_failed",
            error=f"OCR failed: {str(e)}",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )


def extract_text_from_text_file(file_path: str, encoding: str = "utf-8") -> ExtractionResult:
    """
    Extract text from a plain text file.

    Handles various encodings with fallback to latin-1.
    """
    start_time = time.time()

    # Try different encodings
    encodings_to_try = [encoding, "utf-8", "latin-1", "cp1252"]

    for enc in encodings_to_try:
        try:
            with open(file_path, "r", encoding=enc) as f:
                text = f.read()

            processing_time = int((time.time() - start_time) * 1000)
            return ExtractionResult(
                success=True,
                text=text,
                method=f"direct_read_{enc}",
                page_count=1,
                word_count=len(text.split()),
                processing_time_ms=processing_time,
            )
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return ExtractionResult(
                success=False,
                method="direct_read",
                error=f"Failed to read text file: {str(e)}",
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

    return ExtractionResult(
        success=False,
        method="direct_read",
        error="Could not decode file with any supported encoding",
        processing_time_ms=int((time.time() - start_time) * 1000),
    )


def extract_text(file_path: str, content_type: str) -> ExtractionResult:
    """
    Extract text from a file based on its content type.

    Args:
        file_path: Path to the file on disk
        content_type: MIME content type of the file

    Returns:
        ExtractionResult with extracted text or error information
    """
    content_type = content_type.lower()

    # PDF files
    if content_type == "application/pdf":
        return extract_text_from_pdf(file_path)

    # Image files (OCR)
    if content_type.startswith("image/"):
        return extract_text_from_image(file_path)

    # Text files
    if content_type.startswith("text/") or content_type in ("application/json", "application/xml"):
        return extract_text_from_text_file(file_path)

    # Unsupported content type
    return ExtractionResult(
        success=False,
        method="unsupported",
        error=f"Content type '{content_type}' is not supported for text extraction",
    )


def process_document_extraction(document) -> "DocumentContent":
    """
    Process text extraction for a Document and create/update DocumentContent.

    Args:
        document: Document model instance

    Returns:
        DocumentContent instance with extraction results
    """
    from .models import DocumentContent, ExtractionStatus

    # Get or create DocumentContent
    content, created = DocumentContent.objects.get_or_create(document=document)

    # Check if extractable
    if not can_extract(document.content_type):
        content.status = ExtractionStatus.SKIPPED
        content.extraction_method = "not_extractable"
        content.error_message = f"Content type '{document.content_type}' is not extractable"
        content.processed_at = timezone.now()
        content.save()
        return content

    # Mark as processing
    content.status = ExtractionStatus.PROCESSING
    content.save(update_fields=["status", "updated_at"])

    try:
        # Get file path
        file_path = document.file.path

        # Extract text
        result = extract_text(file_path, document.content_type)

        # Update content record
        content.extracted_text = result.text
        content.extraction_method = result.method
        content.page_count = result.page_count
        content.word_count = result.word_count
        content.processing_time_ms = result.processing_time_ms
        content.processed_at = timezone.now()

        if result.success:
            content.status = ExtractionStatus.COMPLETED
            content.error_message = ""
        else:
            content.status = ExtractionStatus.FAILED
            content.error_message = result.error

        content.save()
        return content

    except Exception as e:
        logger.exception(f"Extraction failed for document {document.pk}")
        content.status = ExtractionStatus.FAILED
        content.error_message = str(e)
        content.processed_at = timezone.now()
        content.save()
        return content
