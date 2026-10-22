import asyncio
import logging
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


async def _smtp_config(session) -> dict:
    from scr.dbase.crud_settings import get_setting

    return {
        "host": await get_setting(session, "smtp_host") or "",
        "port": int(await get_setting(session, "smtp_port") or "587"),
        "user": await get_setting(session, "smtp_user") or "",
        "password": await get_setting(session, "smtp_password") or "",
        "from": await get_setting(session, "smtp_from") or "",
    }


async def send_email(session, to: str, subject: str, body: str) -> str | None:
    """Отправляет письмо через SMTP из настроек. Возвращает текст ошибки или None, если отправлено."""
    cfg = await _smtp_config(session)
    if not cfg["host"]:
        logger.warning("SMTP host not configured, skipping email")
        return "Не настроен SMTP-сервер (Настройки → Общие)"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = cfg["from"] or cfg["user"]
    msg["To"] = to

    def _send() -> None:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
            if cfg["user"]:
                server.starttls()
                server.login(cfg["user"], cfg["password"])
            server.send_message(msg)

    try:
        await asyncio.to_thread(_send)
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return "Не удалось отправить письмо"
    return None


async def send_registration_notification(user_email: str, user_name: str) -> None:
    from config import settings

    if not settings.MAIL_TO_REPORT:
        return

    from scr.dbase.database import db_helper

    body = f"Зарегистрирован новый пользователь:\nИмя: {user_name}\nEmail: {user_email}"
    async with db_helper.session_factory() as session:
        await send_email(session, settings.MAIL_TO_REPORT, "Новая регистрация", body)


async def send_password_reset(session, user_email: str, user_name: str, link: str, ttl_hours: int) -> str | None:
    """Письмо со ссылкой на смену пароля. Возвращает текст ошибки или None."""
    body = (
        f"Здравствуйте, {user_name}!\n\n"
        f"Для вас запрошен сброс пароля в «Регистрации ТКП». Чтобы задать новый пароль, перейдите по ссылке:\n"
        f"{link}\n\n"
        f"Ссылка действует {ttl_hours} ч. и только до смены пароля.\n"
        f"Если вы не ожидали это письмо, просто проигнорируйте его."
    )
    return await send_email(session, user_email, "Сброс пароля — Регистрация ТКП", body)
