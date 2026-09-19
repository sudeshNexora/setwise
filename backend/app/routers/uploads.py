import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import faculty_only
from app.models import Upload, User
from app.schemas import UploadOut
from app.services.extractor import extract_text
from app.services.nlp_engine import extract_topics

router = APIRouter(prefix="/api/uploads", tags=["uploads"])
ALLOWED = {".pdf", ".docx", ".doc", ".txt", ".md"}


@router.post("", response_model=UploadOut, status_code=201)
def upload_material(
    file: UploadFile = File(...),
    subject: str = Form(...),
    unit: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(faculty_only),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, f"Upload a PDF, DOCX or TXT file. Got {suffix or 'no extension'}.")

    folder = Path(settings.upload_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}{suffix}"
    with stored.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)

    try:
        text = extract_text(stored)
    except Exception as exc:
        stored.unlink(missing_ok=True)
        raise HTTPException(422, f"Could not read that file: {exc}")

    if len(text.split()) < 60:
        stored.unlink(missing_ok=True)
        raise HTTPException(422, "Too little readable text. If it's a scanned PDF, run OCR first.")

    record = Upload(
        owner_id=user.id,
        filename=file.filename,
        stored_path=str(stored),
        subject=subject,
        unit=unit,
        extracted_text=text,
        topics=extract_topics(text),
        word_count=len(text.split()),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=list[UploadOut])
def list_uploads(db: Session = Depends(get_db), user: User = Depends(faculty_only)):
    return (db.query(Upload)
              .filter(Upload.owner_id == user.id)
              .order_by(Upload.created_at.desc())
              .all())


@router.delete("/{upload_id}", status_code=204)
def delete_upload(upload_id: int, db: Session = Depends(get_db), user: User = Depends(faculty_only)):
    record = db.get(Upload, upload_id)
    if not record or record.owner_id != user.id:
        raise HTTPException(404, "Upload not found.")
    Path(record.stored_path).unlink(missing_ok=True)
    db.delete(record)
    db.commit()
