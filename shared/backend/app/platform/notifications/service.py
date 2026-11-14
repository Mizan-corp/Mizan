"""
Email Service: SMTP (production: Brevo's relay), Resend or SendGrid, and a logged fallback.
Handles invoice PDFs, low-stock alerts and the emails Mizan sends owners (#71, #72).
"""
import asyncio
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


def email_enabled() -> bool:
    """Whether mail really leaves (an SMTP host or a provider key); otherwise it is only logged."""
    from app.core.config import settings

    return bool(settings.EMAIL_SMTP_HOST or RESEND_API_KEY or SENDGRID_API_KEY)


def _smtp_send(to_email: str, subject: str, html_content: str, text: str | None, attachments, reply_to: str | None) -> str:
    """Send one message over SMTP (blocking: run it in a thread). Returns the Message-ID."""
    import re
    import smtplib
    import ssl
    from email.message import EmailMessage
    from email.utils import make_msgid

    from app.core.config import settings

    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    if reply_to or settings.EMAIL_REPLY_TO:
        msg["Reply-To"] = reply_to or settings.EMAIL_REPLY_TO
    domain = settings.EMAIL_FROM.rsplit("@", 1)[-1].strip("> ") or "allmizan.live"
    msg["Message-ID"] = make_msgid(domain=domain)
    plain = text or re.sub(r"\n{3,}", "\n\n", re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", html_content))).strip()
    msg.set_content(plain)
    msg.add_alternative(html_content, subtype="html")
    for att in attachments or []:
        maintype, _, subtype = (att.get("type") or "application/octet-stream").partition("/")
        msg.add_attachment(att["content"], maintype=maintype, subtype=subtype, filename=att["filename"])
    ctx = ssl.create_default_context()
    port = settings.EMAIL_SMTP_PORT
    if port == 465:
        server = smtplib.SMTP_SSL(settings.EMAIL_SMTP_HOST, port, timeout=20, context=ctx)
    else:
        server = smtplib.SMTP(settings.EMAIL_SMTP_HOST, port, timeout=20)
        if settings.EMAIL_SMTP_TLS:
            server.starttls(context=ctx)
    try:
        if settings.EMAIL_SMTP_USER:
            server.login(settings.EMAIL_SMTP_USER, settings.EMAIL_SMTP_PASSWORD)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass
    return msg["Message-ID"]


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    attachments: Optional[List[dict]] = None,
    text: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> dict:
    """
    Sends email over SMTP, Resend or SendGrid, or logs it when none is configured.
    attachments: list of {"filename": "invoice.pdf", "content": bytes, "type": "application/pdf"}
    """
    from app.core.config import settings

    if settings.EMAIL_SMTP_HOST:
        try:
            mid = await asyncio.to_thread(_smtp_send, to_email, subject, html_content, text, attachments, reply_to)
            logger.info("Email sent to %s over SMTP: %s (%s)", to_email, subject, mid)
            return {"ok": True, "provider": "smtp", "id": mid}
        except Exception as e:
            logger.error("Failed to send email over SMTP to %s: %s", to_email, e)
            return {"ok": False, "provider": "smtp", "error": str(e)}

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

    from app.platform.auth.models.user import User

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
