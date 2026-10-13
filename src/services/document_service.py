"""Document and KYC management service for LoanPulse (Phase 6).

Handles secure file upload, extension/size validation, isolated document storage,
access control checks, and KYC workflow transitions.
"""
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Tuple, Optional
from werkzeug.utils import secure_filename

from src.models import db, User, CustomerDocument, Notification

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_DOCUMENT_TYPES = {
    "IDENTITY_PROOF": "Government Issued Identity Proof (Passport, Driving License, National ID)",
    "ADDRESS_PROOF": "Proof of Address (Utility Bill, Bank Statement)",
    "INCOME_PROOF": "Income Proof (Salary Slip, Tax Return, Bank Statement)",
}


def allowed_file(filename: str) -> bool:
    """Check if the provided filename has an approved extension."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def get_file_extension(filename: str) -> str:
    """Extract lowercased extension."""
    if "." in filename:
        return filename.rsplit(".", 1)[1].lower()
    return ""


def save_customer_document(
    customer_id: int,
    document_type: str,
    file_storage,
    upload_folder: str,
) -> CustomerDocument:
    """Validate, secure, and save an uploaded customer document."""
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError(f"Invalid document type: {document_type}. Allowed: {list(ALLOWED_DOCUMENT_TYPES.keys())}")

    if not file_storage or not file_storage.filename or file_storage.filename.strip() == "":
        raise ValueError("No file selected for upload.")

    orig_filename = secure_filename(file_storage.filename)
    if not allowed_file(orig_filename):
        raise ValueError(f"Unsupported file type. Only PDF, PNG, and JPG files are accepted.")

    # Read data or check length
    file_storage.seek(0, os.SEEK_END)
    file_size = file_storage.tell()
    file_storage.seek(0)

    if file_size <= 0:
        raise ValueError("The uploaded file is empty.")

    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"File size exceeds maximum limit of 5 MB ({file_size / (1024*1024):.2f} MB).")

    ext = get_file_extension(orig_filename)
    unique_token = uuid.uuid4().hex[:12]
    safe_stored_name = f"cust_{customer_id}_{document_type.lower()}_{unique_token}.{ext}"

    os.makedirs(upload_folder, exist_ok=True)
    destination_path = os.path.join(upload_folder, safe_stored_name)
    file_storage.save(destination_path)

    # Detect MIME type
    mime_type = file_storage.mimetype or "application/octet-stream"

    # Check if a document of this type already exists for customer
    existing_doc = CustomerDocument.query.filter_by(
        customer_id=customer_id,
        document_type=document_type,
    ).first()

    if existing_doc:
        # Remove old physical file if exists and different
        if existing_doc.file_path and os.path.exists(existing_doc.file_path) and existing_doc.file_path != destination_path:
            try:
                os.remove(existing_doc.file_path)
            except OSError:
                pass
        
        existing_doc.original_filename = orig_filename
        existing_doc.stored_filename = safe_stored_name
        existing_doc.file_path = destination_path
        existing_doc.file_size = file_size
        existing_doc.mime_type = mime_type
        existing_doc.verification_status = "PENDING"
        existing_doc.rejection_reason = None
        existing_doc.uploaded_at = date.today()
        existing_doc.reviewed_at = None
        db.session.commit()
        return existing_doc

    doc_record = CustomerDocument(
        customer_id=customer_id,
        document_type=document_type,
        original_filename=orig_filename,
        stored_filename=safe_stored_name,
        file_path=destination_path,
        file_size=file_size,
        mime_type=mime_type,
        verification_status="PENDING",
        rejection_reason=None,
        uploaded_at=date.today(),
        reviewed_at=None,
    )
    db.session.add(doc_record)
    db.session.commit()
    return doc_record


def delete_customer_document(document_id: int, customer_id: int) -> bool:
    """Delete a customer document record and its associated physical file."""
    doc = CustomerDocument.query.filter_by(document_id=document_id, customer_id=customer_id).first()
    if not doc:
        return False

    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError:
            pass

    db.session.delete(doc)
    db.session.commit()
    return True


def can_access_document(user: User, document: CustomerDocument) -> bool:
    """Check if the requesting user has permission to view/download the document."""
    if not user or not user.is_authenticated:
        return False
    if user.role in ("LOAN_OFFICER", "LOAN_MANAGER"):
        return True
    if user.role == "CUSTOMER" and user.user_id == document.customer_id:
        return True
    return False


def submit_customer_kyc(customer: User) -> Tuple[bool, str]:
    """Submit customer KYC for officer verification."""
    docs = CustomerDocument.query.filter_by(customer_id=customer.user_id).all()
    if not docs:
        return False, "Please upload at least one verification document before submitting KYC."

    customer.kyc_status = "PENDING"
    customer.kyc_rejection_reason = None
    customer.kyc_submitted_at = date.today()
    customer.kyc_reviewed_at = None

    for doc in docs:
        if doc.verification_status != "VERIFIED":
            doc.verification_status = "PENDING"
            doc.rejection_reason = None

    # Customer notification
    notif = Notification(
        application_id="KYC-SUBMISSION",
        recipient_user_id=customer.user_id,
        old_status=None,
        new_status="KYC_PENDING",
        message="Your KYC verification request has been submitted for review.",
        created_at=date.today(),
        is_read=False,
    )
    db.session.add(notif)
    db.session.commit()
    return True, "KYC documents submitted successfully for verification."


def review_customer_kyc(
    customer: User,
    officer: User,
    action: str,
    rejection_reason: Optional[str] = None,
) -> Tuple[bool, str]:
    """Process officer decision (VERIFY or REJECT) on customer KYC."""
    if action == "VERIFY":
        customer.kyc_status = "VERIFIED"
        customer.kyc_rejection_reason = None
        customer.kyc_reviewed_at = date.today()

        docs = CustomerDocument.query.filter_by(customer_id=customer.user_id).all()
        for doc in docs:
            doc.verification_status = "VERIFIED"
            doc.reviewed_at = date.today()
            doc.rejection_reason = None

        notif = Notification(
            application_id="KYC-VERIFICATION",
            recipient_user_id=customer.user_id,
            old_status="KYC_PENDING",
            new_status="KYC_VERIFIED",
            message="Congratulations! Your KYC documents have been successfully verified.",
            created_at=date.today(),
            is_read=False,
        )
        db.session.add(notif)
        db.session.commit()
        return True, f"KYC for customer {customer.full_name} has been verified."

    elif action == "REJECT":
        if not rejection_reason or not rejection_reason.strip():
            return False, "A rejection reason is required when rejecting KYC."

        customer.kyc_status = "REJECTED"
        customer.kyc_rejection_reason = rejection_reason.strip()
        customer.kyc_reviewed_at = date.today()

        docs = CustomerDocument.query.filter_by(customer_id=customer.user_id).all()
        for doc in docs:
            doc.verification_status = "REJECTED"
            doc.reviewed_at = date.today()
            doc.rejection_reason = rejection_reason.strip()

        notif = Notification(
            application_id="KYC-VERIFICATION",
            recipient_user_id=customer.user_id,
            old_status="KYC_PENDING",
            new_status="KYC_REJECTED",
            message=f"Your KYC verification was rejected. Reason: {rejection_reason.strip()}",
            created_at=date.today(),
            is_read=False,
        )
        db.session.add(notif)
        db.session.commit()
        return True, f"KYC for customer {customer.full_name} has been rejected."

    return False, f"Unknown action: {action}"
