"""Desktop notifications for booking results (cross-platform)."""

from .platform_utils import send_notification


def notify(title: str, message: str):
    send_notification(title, message)
