from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AuditEvent, DeadLetter, Document, DocumentStatus
from app.exports import append_to_google_sheet, approved_csv
from app.schemas import ApprovalRequest, AuditRead, DeadLetterRead, DocumentCorrection, DocumentRead, ExportResult
from app.service import audit, ingest

router = APIRouter(prefix="/api/v1")


@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED,
             summary="Ingest a synthetic invoice or receipt")
async def create_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or file.filename.lower().rsplit(".", 1)[-1] not in {"pdf", "txt", "json"}:
        raise HTTPException(415, "Supported formats: PDF, TXT, JSON")
    data = await file.read(get_settings().max_upload_bytes + 1)
    if len(data) > get_settings().max_upload_bytes:
        raise HTTPException(413, "File exceeds upload limit")
    try:
        return ingest(db, file.filename, data)
    except ValueError as exc:
        raise HTTPException(422, f"Document could not be parsed: {exc}") from exc


@router.get("/documents", response_model=list[DocumentRead], summary="List records or the review queue")
def list_documents(status_filter: DocumentStatus | None = Query(None, alias="status"), db: Session = Depends(get_db)):
    query = select(Document).order_by(Document.created_at.desc())
    if status_filter:
        query = query.where(Document.status == status_filter)
    return list(db.scalars(query))


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    return document


@router.patch("/documents/{document_id}", response_model=DocumentRead, summary="Correct a review record")
def correct_document(document_id: str, correction: DocumentCorrection, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    changes = correction.model_dump(exclude_unset=True, exclude={"actor"})
    before = {key: str(getattr(document, key)) for key in changes}
    for key, value in changes.items():
        setattr(document, key, value)
    audit(db, document.id, "corrected", correction.actor, {"before": before, "changed_fields": list(changes)})
    db.commit()
    db.refresh(document)
    return document


@router.post("/documents/{document_id}/approve", response_model=DocumentRead, summary="Approve a reviewed record")
def approve_document(document_id: str, request: ApprovalRequest, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    if document.status == DocumentStatus.DUPLICATE:
        raise HTTPException(409, "Duplicate records cannot be approved")
    missing = [name for name in ("vendor", "amount", "document_date", "document_number") if not getattr(document, name)]
    if missing:
        raise HTTPException(422, {"missing_fields": missing})
    document.status = DocumentStatus.APPROVED
    document.approved_at = datetime.now(UTC)
    audit(db, document.id, "approved", request.actor)
    db.commit()
    db.refresh(document)
    return document


@router.get("/documents/{document_id}/audit", response_model=list[AuditRead])
def document_audit(document_id: str, db: Session = Depends(get_db)):
    if not db.get(Document, document_id):
        raise HTTPException(404, "Document not found")
    return list(db.scalars(select(AuditEvent).where(AuditEvent.document_id == document_id).order_by(AuditEvent.created_at)))


@router.get("/dead-letters", response_model=list[DeadLetterRead], summary="Inspect parsing failures")
def list_dead_letters(db: Session = Depends(get_db)):
    return list(db.scalars(select(DeadLetter).order_by(DeadLetter.created_at.desc())))


@router.post(
    "/dead-letters/{dead_letter_id}/retry",
    response_model=DocumentRead,
    summary="Retry a failed extraction",
)
def retry_dead_letter(dead_letter_id: str, db: Session = Depends(get_db)):
    dead_letter = db.get(DeadLetter, dead_letter_id)
    if not dead_letter:
        raise HTTPException(404, "Dead letter not found")
    filename, payload = dead_letter.filename, dead_letter.payload
    dead_letter.retry_count += 1
    dead_letter.updated_at = datetime.now(UTC)
    db.commit()
    try:
        document = ingest(db, filename, payload)
    except ValueError as exc:
        replacement = db.scalar(
            select(DeadLetter).where(DeadLetter.content_hash == dead_letter.content_hash)
            .order_by(DeadLetter.created_at.desc())
        )
        if replacement and replacement.id != dead_letter.id:
            db.delete(replacement)
        dead_letter.error = str(exc)
        db.commit()
        raise HTTPException(422, f"Retry failed: {exc}") from exc
    db.delete(dead_letter)
    audit(db, document.id, "retried_from_dead_letter", details={"retry_count": dead_letter.retry_count})
    db.commit()
    db.refresh(document)
    return document


@router.get(
    "/exports/approved.csv",
    summary="Download approved records as CSV",
    response_class=Response,
)
def export_approved_csv(db: Session = Depends(get_db)):
    documents = list(db.scalars(
        select(Document)
        .where(Document.status == DocumentStatus.APPROVED)
        .order_by(Document.approved_at, Document.id)
    ))
    for document in documents:
        audit(db, document.id, "exported_csv", details={"destination": "download"})
    db.commit()
    return Response(
        content=approved_csv(documents),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="approved-records.csv"'},
    )


@router.post(
    "/exports/google-sheets",
    response_model=ExportResult,
    summary="Append approved, unexported records to Google Sheets",
)
def export_google_sheets(db: Session = Depends(get_db)):
    settings = get_settings()
    credentials_file = settings.google_sheets_credentials_file
    spreadsheet_id = settings.google_sheets_spreadsheet_id
    if not credentials_file or not spreadsheet_id:
        raise HTTPException(503, "Google Sheets export is not configured")
    if not Path(credentials_file).is_file():
        raise HTTPException(503, "Google Sheets credentials file was not found")
    already_exported = exists().where(
        AuditEvent.document_id == Document.id,
        AuditEvent.action == "exported_google_sheets",
    )
    documents = list(db.scalars(
        select(Document)
        .where(Document.status == DocumentStatus.APPROVED, ~already_exported)
        .order_by(Document.approved_at, Document.id)
    ))
    approved_count = db.scalar(
        select(func.count(Document.id)).where(Document.status == DocumentStatus.APPROVED)
    ) or 0
    if not documents:
        return ExportResult(
            destination="google_sheets",
            exported_count=0,
            skipped_count=approved_count,
            spreadsheet_id=spreadsheet_id,
        )
    try:
        exported_count = append_to_google_sheet(
            documents,
            credentials_file=Path(credentials_file),
            spreadsheet_id=spreadsheet_id,
            range_name=settings.google_sheets_range,
        )
    except Exception as exc:
        raise HTTPException(502, f"Google Sheets export failed: {exc}") from exc
    for document in documents:
        audit(db, document.id, "exported_google_sheets", details={"spreadsheet_id": spreadsheet_id})
    db.commit()
    return ExportResult(
        destination="google_sheets",
        exported_count=exported_count,
        skipped_count=approved_count - exported_count,
        spreadsheet_id=spreadsheet_id,
    )
