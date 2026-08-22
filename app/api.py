from pathlib import Path
from secrets import compare_digest

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.document_lifecycle import (
    ApprovalFieldsMissing,
    DeadLetterNotFound,
    DocumentChanges,
    DocumentIntakeLifecycle,
    DocumentNotFound,
    DuplicateCannotBeApproved,
    ParseFailed,
    RetryFailed,
)
from app.exports import append_to_google_sheet, approved_csv
from app.models import AuditEvent, DeadLetter, Document, DocumentStatus
from app.schemas import (
    ApprovalRequest,
    AuditRead,
    DeadLetterRead,
    DocumentCorrection,
    DocumentRead,
    ExportResult,
)

router = APIRouter(prefix="/api/v1")


def require_n8n_key(x_ledgerline_key: str | None = Header(None)) -> None:
    expected = get_settings().n8n_api_key
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "n8n integration is not configured")
    if not x_ledgerline_key or not compare_digest(x_ledgerline_key, expected):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid integration credential",
            headers={"WWW-Authenticate": "ApiKey"},
        )


async def ingest_upload(file: UploadFile, db: Session) -> Document:
    if not file.filename or file.filename.lower().rsplit(".", 1)[-1] not in {"pdf", "txt", "json"}:
        raise HTTPException(415, "Supported formats: PDF, TXT, JSON")
    data = await file.read(get_settings().max_upload_bytes + 1)
    if len(data) > get_settings().max_upload_bytes:
        raise HTTPException(413, "File exceeds upload limit")
    try:
        return DocumentIntakeLifecycle(db).intake(file.filename, data)
    except ParseFailed as exc:
        raise HTTPException(422, f"Document could not be parsed: {exc}") from exc


@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED,
             summary="Ingest a synthetic invoice or receipt")
async def create_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    return await ingest_upload(file, db)


@router.post(
    "/integrations/n8n/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_n8n_key)],
    summary="Ingest a document from the private n8n orchestrator",
)
async def create_n8n_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    return await ingest_upload(file, db)


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
    try:
        return DocumentIntakeLifecycle(db).correct(
            document_id,
            DocumentChanges(correction.model_dump(exclude_unset=True, exclude={"actor"})),
            actor=correction.actor,
        )
    except DocumentNotFound as exc:
        raise HTTPException(404, "Document not found") from exc


@router.post("/documents/{document_id}/approve", response_model=DocumentRead, summary="Approve a reviewed record")
def approve_document(document_id: str, request: ApprovalRequest, db: Session = Depends(get_db)):
    try:
        return DocumentIntakeLifecycle(db).approve(document_id, actor=request.actor)
    except DocumentNotFound as exc:
        raise HTTPException(404, "Document not found") from exc
    except DuplicateCannotBeApproved as exc:
        raise HTTPException(409, "Duplicate records cannot be approved") from exc
    except ApprovalFieldsMissing as exc:
        raise HTTPException(422, {"missing_fields": exc.missing_fields}) from exc


@router.get("/documents/{document_id}/audit", response_model=list[AuditRead])
def document_audit(document_id: str, db: Session = Depends(get_db)):
    try:
        return DocumentIntakeLifecycle(db).audit(document_id)
    except DocumentNotFound as exc:
        raise HTTPException(404, "Document not found") from exc


@router.get("/dead-letters", response_model=list[DeadLetterRead], summary="Inspect parsing failures")
def list_dead_letters(db: Session = Depends(get_db)):
    return list(db.scalars(select(DeadLetter).order_by(DeadLetter.created_at.desc())))


@router.post(
    "/dead-letters/{dead_letter_id}/retry",
    response_model=DocumentRead,
    summary="Retry a failed extraction",
)
def retry_dead_letter(dead_letter_id: str, db: Session = Depends(get_db)):
    try:
        return DocumentIntakeLifecycle(db).retry(dead_letter_id)
    except DeadLetterNotFound as exc:
        raise HTTPException(404, "Dead letter not found") from exc
    except RetryFailed as exc:
        raise HTTPException(422, f"Retry failed: {exc}") from exc


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
        db.add(AuditEvent(
            document_id=document.id,
            action="exported_csv",
            details={"destination": "download"},
        ))
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
        db.add(AuditEvent(
            document_id=document.id,
            action="exported_google_sheets",
            details={"spreadsheet_id": spreadsheet_id},
        ))
    db.commit()
    return ExportResult(
        destination="google_sheets",
        exported_count=exported_count,
        skipped_count=approved_count - exported_count,
        spreadsheet_id=spreadsheet_id,
    )
