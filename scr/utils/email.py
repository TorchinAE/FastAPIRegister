import asyncio
import logging
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


async def send_registration_notification(user_email: str, user_name: str) -> None:
    from config import settings

    if not settings.MAIL_TO_REPORT:
        return

    from scr.dbase.crud_settings import get_setting
    from scr.dbase.database import db_helper

    async with db_helper.session_factory() as session:
        smtp_host = await get_setting(session, "smtp_host") or ""
        smtp_port = int(await get_setting(session, "smtp_port") or "587")
        smtp_user = await get_setting(session, "smtp_user") or ""
        smtp_password = await get_setting(session, "smtp_password") or ""
        smtp_from = await get_setting(session, "smtp_from") or ""

    if not smtp_host:
        logger.warning("SMTP host not configured, skipping notification email")
        return

    body = f"Зарегистрирован новый пользователь:\nИмя: {user_name}\nEmail: {user_email}"
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "Новая регистрация"
    msg["From"] = smtp_from or smtp_user
    msg["To"] = settings.MAIL_TO_REPORT

    def _send() -> None:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_user:
                server.starttls()
                server.login(smtp_user, smtp_password)
            server.send_message(msg)

    try:
        await asyncio.to_thread(_send)
    except Exception:
        logger.exception("Failed to send registration notification email")
