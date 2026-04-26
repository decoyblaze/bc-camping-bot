"""Precise time synchronization using NTP for exact 7:00 AM PT execution."""

import time
from datetime import datetime, timedelta

import ntplib
from rich.console import Console

console = Console()

NTP_SERVERS = [
    "time.google.com",
    "time.cloudflare.com",
    "pool.ntp.org",
]


def get_ntp_offset() -> float:
    """Get the offset between local clock and NTP time."""
    for server in NTP_SERVERS:
        try:
            client = ntplib.NTPClient()
            response = client.request(server, version=3)
            offset = response.offset
            console.print(f"[green]NTP sync with {server}: offset = {offset:.4f}s[/green]")
            return offset
        except Exception:
            continue
    console.print("[dim]NTP unavailable — using system clock (this is fine).[/dim]")
    return 0.0


def precise_time(offset: float = 0.0) -> datetime:
    """Get current time adjusted by NTP offset."""
    return datetime.now() + timedelta(seconds=offset)


def wait_until(target: datetime, offset: float = 0.0):
    """Wait precisely until the target time using NTP-corrected clock.

    Uses coarse sleep until 2 seconds before target, then busy-waits
    for sub-millisecond precision.
    """
    while True:
        now = precise_time(offset)
        remaining = (target - now).total_seconds()

        if remaining <= 0:
            return

        if remaining > 2:
            console.print(
                f"[dim]Waiting... {remaining:.1f}s remaining "
                f"(target: {target.strftime('%H:%M:%S')})[/dim]",
                end="\r",
            )
            time.sleep(min(remaining - 2, 1.0))
        elif remaining > 0.01:
            time.sleep(0.001)
        # Under 10ms: busy-wait for maximum precision
