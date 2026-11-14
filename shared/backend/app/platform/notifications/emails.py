"""The emails Mizan sends owners (#71, #72): codes, receipts and billing reminders.

Arabic, right to left, in Mizan's colours; plain tables and inline styles so mail apps (Gmail,
Outlook, phones) show them as intended. Each function returns (subject, html, text).
"""
from __future__ import annotations

from html import escape

WINE = "#7a1f3d"
INK = "#1d1b1a"
MUTE = "#6f6964"


def _layout(title: str, body: str, action: tuple[str, str] | None = None, footer: str = "") -> str:
    button = ""
    if action:
        label, url = action
        button = (f'<tr><td style="padding:8px 32px 24px"><a href="{escape(url)}" style="display:inline-block;background:{WINE};'
                  f'color:#ffffff;text-decoration:none;font-weight:bold;padding:12px 22px;border-radius:10px">{escape(label)}</a></td></tr>')
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{escape(title)}</title></head>
<body style="margin:0;padding:0;background:#f6f3f0;font-family:Tahoma,Arial,sans-serif;color:{INK}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f3f0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e9e3de" dir="rtl">
<tr><td style="background:#2a1019;padding:18px 32px;color:#ffffff;font-size:20px;font-weight:bold;text-align:right">ميزان</td></tr>
<tr><td style="padding:28px 32px 8px;text-align:right"><h1 style="margin:0 0 12px;font-size:20px;color:{INK}">{escape(title)}</h1>
<div style="font-size:15px;line-height:1.8;color:{INK}">{body}</div></td></tr>
{button}
<tr><td style="padding:16px 32px 24px;border-top:1px solid #efe9e4;font-size:12px;line-height:1.7;color:{MUTE};text-align:right">
{footer or "وصلتك هذه الرسالة لأن هذا البريد مسجّل في حسابك على ميزان."}<br>ميزان · <a href="https://allmizan.live" style="color:{MUTE}">allmizan.live</a></td></tr>
</table></td></tr></table></body></html>"""


def _code(code: str) -> str:
    spaced = f"{code[:3]} {code[3:]}"
    return (f'<p style="margin:18px 0;text-align:center"><span dir="ltr" style="display:inline-block;font-family:Consolas,Menlo,monospace;'
            f'font-size:30px;letter-spacing:6px;font-weight:bold;background:#f6ecef;color:{WINE};padding:12px 22px;border-radius:12px">{spaced}</span></p>')


def code_email(name: str, code: str, purpose: str, minutes: int) -> tuple[str, str, str]:
    first = escape((name or "").split(" ")[0] or "")
    if purpose == "reset_password":
        subject = f"رمز استعادة كلمة المرور في ميزان: {code}"
        title = "استعادة كلمة المرور"
        intro = "طلبتَ استعادة كلمة مرور حسابك على ميزان. اكتب هذا الرمز في صفحة الدخول:"
        warn = "إن لم تطلب ذلك فتجاهل هذه الرسالة؛ كلمة مرورك الحالية تبقى كما هي."
    else:
        subject = f"رمز تأكيد بريدك في ميزان: {code}"
        title = "تأكيد بريدك الإلكتروني"
        intro = "لتأكيد هذا البريد لحسابك على ميزان، اكتب هذا الرمز:"
        warn = "إن لم تسجّل في ميزان فتجاهل هذه الرسالة."
    body = (f"<p>مرحبًا {first}،</p><p>{intro}</p>{_code(code)}"
            f"<p style='color:{MUTE};font-size:13px'>الرمز صالح {minutes} دقيقة ولمرة واحدة. لا تشاركه مع أحد؛ فريق ميزان لن يطلبه منك.</p>"
            f"<p style='color:{MUTE};font-size:13px'>{warn}</p>")
    text = (f"مرحبًا {name},\n\n{intro}\n\n{code}\n\nالرمز صالح {minutes} دقيقة ولمرة واحدة. لا تشاركه مع أحد.\n{warn}\n\nميزان · allmizan.live")
    return subject, _layout(title, body), text


def receipt_email(name: str, workspace: str, ref: str, amount: str, plan: str, period: str, url: str) -> tuple[str, str, str]:
    subject = f"إيصال دفع ميزان {ref}"
    rows = "".join(f'<tr><td style="padding:6px 0;color:{MUTE}">{k}</td><td style="padding:6px 0;font-weight:bold">{escape(v)}</td></tr>'
                   for k, v in (("المنشأة", workspace), ("الباقة", plan), ("الفترة", period), ("المبلغ", amount), ("رقم الفاتورة", ref)))
    body = (f"<p>مرحبًا {escape((name or '').split(' ')[0])}،</p><p>استلمنا دفعتك، شكرًا لك. الإيصال مرفق بهذه الرسالة.</p>"
            f'<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;font-size:14px">{rows}</table>')
    text = f"استلمنا دفعتك، شكرًا لك.\nالمنشأة: {workspace}\nالباقة: {plan}\nالفترة: {period}\nالمبلغ: {amount}\nرقم الفاتورة: {ref}\n\nالإيصال مرفق.\nميزان · allmizan.live"
    return subject, _layout("تم استلام دفعتك", body, ("فواتيري في لوحة المالك", url)), text


def reminder_email(kind: str, name: str, workspace: str, days: int, url: str) -> tuple[str, str, str]:
    first = escape((name or "").split(" ")[0])
    ws = escape(workspace)
    when = "اليوم" if days <= 0 else ("غدًا" if days == 1 else f"بعد {days} أيام")
    if kind == "trial_ending":
        subject, title = f"تنتهي التجربة المجانية لـ{workspace} {when}", "تنتهي فترتك التجريبية قريبًا"
        msg = (f"تنتهي الفترة التجريبية لمنشأة <b>{ws}</b> {when}. اختر باقة الآن لتستمر في العمل دون توقف؛ "
               "بياناتك كلها تبقى كما هي.")
        action = "اختر باقة"
    elif kind == "trial_expired":
        subject, title = f"انتهت التجربة المجانية لـ{workspace}", "انتهت الفترة التجريبية"
        msg = (f"انتهت الفترة التجريبية لمنشأة <b>{ws}</b>، وصارت للقراءة فقط. بياناتك محفوظة؛ "
               "اختر باقة لتعود إلى البيع والتسجيل فورًا.")
        action = "اختر باقة"
    elif kind == "paid_ending":
        subject, title = f"يحين تجديد اشتراك {workspace} {when}", "موعد التجديد يقترب"
        msg = f"ينتهي اشتراك منشأة <b>{ws}</b> {when}. جدّده الآن ليستمر العمل دون انقطاع."
        action = "جدّد الاشتراك"
    else:  # paid_expired
        subject, title = f"انتهى اشتراك {workspace}", "انتهى الاشتراك"
        msg = f"انتهى اشتراك منشأة <b>{ws}</b> وصارت للقراءة فقط. بياناتك محفوظة؛ جدّد الاشتراك لتعود إلى العمل فورًا."
        action = "جدّد الاشتراك"
    body = f"<p>مرحبًا {first}،</p><p>{msg}</p>"
    text = f"مرحبًا {name},\n\n{title}: {workspace}.\n{url}\n\nميزان · allmizan.live"
    return subject, _layout(title, body, (action, url)), text
