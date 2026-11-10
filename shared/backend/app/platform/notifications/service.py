"""
Email Service: supports SendGrid, Resend, and simulated SMTP fallback.
Handles sending invoice PDFs and low-stock alerts.
"""
import os
import logging
import base64
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger("mizan.email")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "invoices@mizan.app")
ENABLE_EMAIL_NOTIFICATIONS = os.getenv("ENABLE_EMAIL_NOTIFICATIONS", "false").lower() in ("true", "1", "yes")


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    attachments: Optional[List[dict]] = None,
) -> dict:
    """
    Sends email using Resend, SendGrid, or fallback simulated logger.
    attachments: list of {"filename": "invoice.pdf", "content": bytes, "type": "application/pdf"}
    """
    if RESEND_API_KEY:
        try:
            import urllib.request
            import json

            payload = {
                "from": SENDER_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }
            if attachments:
                payload["attachments"] = [
                    {
                        "filename": att["filename"],
                        "content": base64.b64encode(att["content"]).decode("ascii"),
                    }
                    for att in attachments
                ]
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=data,
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                logger.info("Resend email sent to %s: %s", to_email, resp_data)
                return {"ok": True, "provider": "resend", "id": resp_data.get("id")}
        except Exception as e:
            logger.error("Failed to send email via Resend: %s", e)
            return {"ok": False, "provider": "resend", "error": str(e)}

    if SENDGRID_API_KEY:
        try:
            import urllib.request
            import json

            payload = {
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": SENDER_EMAIL},
                "subject": subject,
                "content": [{"type": "text/html", "value": html_content}],
            }
            if attachments:
                payload["attachments"] = [
                    {
                        "filename": att["filename"],
                        "content": base64.b64encode(att["content"]).decode("ascii"),
                        "type": att.get("type", "application/pdf"),
                        "disposition": "attachment",
                    }
                    for att in attachments
                ]
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                "https://api.sendgrid.com/v3/mail/send",
                data=data,
                headers={
                    "Authorization": f"Bearer {SENDGRID_API_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info("SendGrid email sent to %s: status %d", to_email, resp.status)
                return {"ok": True, "provider": "sendgrid", "status": resp.status}
        except Exception as e:
            logger.error("Failed to send email via SendGrid: %s", e)
            return {"ok": False, "provider": "sendgrid", "error": str(e)}

    # Simulated / Log Fallback (Development & Staging environments)
    logger.info(
        "[SIMULATED EMAIL] To: %s | Subject: %s | Attachments: %d bytes (Provider: None configured, simulated delivery)",
        to_email,
        subject,
        sum(len(a.get("content", b"")) for a in (attachments or [])),
    )
    return {
        "ok": True,
        "provider": "simulated",
        "detail": f"تمت محاكاة إرسال البريد الإلكتروني بنجاح إلى {to_email}",
    }


async def send_low_stock_email_alert(db: AsyncSession, tenant_id, low_stock_items: List[Tuple]):
    """Send low-stock email summary to managers if enabled."""
    if not ENABLE_EMAIL_NOTIFICATIONS and not RESEND_API_KEY and not SENDGRID_API_KEY:
        return

    from app.models.user import User

    manager_stmt = select(User.username).where(
        User.tenant_id == tenant_id if tenant_id else True,
        User.role.in_(["manager", "admin"]),
        User.is_active.is_(True),
    )
    emails = (await db.execute(manager_stmt)).scalars().all()
    recipients = [e for e in emails if "@" in e]
    if not recipients:
        return

    items_html = "".join(
        f"<li><b>{p.name}</b>: الرصيد الحالي {q} (الحد الأدنى: {th})</li>"
        for p, q, th in low_stock_items
    )
    body = f"""
    <div dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <h2 style="color: #b45309;">تنبيه نواقص المخزون — منصة ميزان</h2>
      <p>نحيطكم علماً بأن المنتجات التالية وصلت إلى أو قلت عن حد إعادة الطلب:</p>
      <ul>{items_html}</ul>
      <p>يُرجى اتخاذ الإجراء اللازم وإصدار أوامر التوريد.</p>
    </div>
    """
    for recipient in recipients:
        await send_email(recipient, "تنبيه انخفاض المخزون — ميزان ERP", body)
