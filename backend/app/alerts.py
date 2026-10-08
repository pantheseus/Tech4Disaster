"""Alert stub. Prints to console; sends email if SMTP is configured.
Swap in Twilio / Fast2SMS / Telegram bot here if your idea needs real SMS."""
import smtplib
from email.message import EmailMessage

from . import config


def send_alert(level: str, message: str) -> dict:
    print(f"[ALERT:{level.upper()}] {message}")
    result = {"console": True, "email": False}
    if config.SMTP_HOST and config.ALERT_EMAIL_TO:
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[{level.upper()}] Disaster alert"
            msg["From"] = config.SMTP_USER
            msg["To"] = config.ALERT_EMAIL_TO
            msg.set_content(message)
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
                s.starttls()
                s.login(config.SMTP_USER, config.SMTP_PASS)
                s.send_message(msg)
            result["email"] = True
        except Exception as e:
            print(f"[alerts] email failed: {e}")
    return result
