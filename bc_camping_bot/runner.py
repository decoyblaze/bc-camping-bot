"""Main entry point — orchestrates timing, browser launch, and booking execution.

Strategy for sub-1-second booking:
1. Launch browser 2 min early, load homepage to warm session
2. At ~60s before 7 AM, pre-navigate to results URL (caches all JS/CSS/API)
3. At exactly 7:00:00.000 PT, reload the results page (cache hit = fast)
4. Select area → Add to stay → Reserve (3 clicks, zero delay)
5. If fast path fails: reload retry, then form fallback
"""

import asyncio
import sys
from datetime import datetime, timedelta

from playwright.async_api import async_playwright
from rich.console import Console
from rich.panel import Panel

from .booker import (
    build_results_url,
    load_session,
    pre_navigate,
)
from .config import Booking, load_config
from .notify import notify
from .stealth import apply_stealth
from .timesync import get_ntp_offset, precise_time, wait_until

console = Console()

LEAD_TIME_SECONDS = 120


async def run_booking(booking: Booking, dry_run: bool = False, force: bool = False):
    """Run a single booking attempt with NTP-synced timing."""
    console.print(Panel(
        f"[bold]{booking.name}[/bold]\n"
        f"Park: {booking.park}\n"
        f"Campsite: {booking.campsite}\n"
        f"Arrival: {booking.arrival_date}\n"
        f"Nights: {booking.num_nights}\n"
        f"People: {booking.num_people}\n"
        f"Opens at: {booking.booking_opens_at.strftime('%Y-%m-%d %H:%M:%S')} PT\n"
        f"Direct URL: {build_results_url(booking)[:80]}...",
        title="Booking Details",
    ))

    ntp_offset = get_ntp_offset()
    now = precise_time(ntp_offset)
    target = booking.booking_opens_at

    if not force:
        if now > target + timedelta(seconds=30):
            console.print("[bold red]Booking window already passed. Attempting anyway...[/bold red]")
        elif now < target - timedelta(hours=12):
            console.print(
                f"[yellow]Booking window opens in {(target - now).total_seconds() / 3600:.1f} hours.[/yellow]\n"
                f"[yellow]Re-run this closer to {target.strftime('%Y-%m-%d %H:%M')} PT.[/yellow]"
            )
            return False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        try:
            context = await load_session(browser.new_context, booking)
            page = await context.new_page()
            await apply_stealth(page)

            if not force:
                launch_at = target - timedelta(seconds=LEAD_TIME_SECONDS)
                if precise_time(ntp_offset) < launch_at:
                    console.print(
                        f"[dim]Waiting to launch browser at "
                        f"{launch_at.strftime('%H:%M:%S')}...[/dim]"
                    )
                    wait_until(launch_at, ntp_offset)

            console.print("[blue]Loading camping.bcparks.ca to warm session...[/blue]")
            await page.goto("https://camping.bcparks.ca", wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")
            console.print("[green]Site loaded. Session warm.[/green]")

            if not dry_run:
                pre_load_at = target - timedelta(seconds=30)
                remaining_to_pre = (pre_load_at - precise_time(ntp_offset)).total_seconds()
                if remaining_to_pre > 0 and not force:
                    console.print(f"[dim]Waiting {remaining_to_pre:.0f}s to pre-load results...[/dim]")
                    wait_until(pre_load_at, ntp_offset)

                console.print("[blue]Pre-loading results page (caching assets)...[/blue]")
                await pre_navigate(page, booking)
                console.print("[green]Results page cached. Standing by.[/green]")

            if not force:
                remaining = (target - precise_time(ntp_offset)).total_seconds()
                if remaining > 0:
                    console.print(
                        f"[bold cyan]Waiting for 7:00 AM... "
                        f"{remaining:.1f}s remaining[/bold cyan]"
                    )
                    wait_until(target, ntp_offset)

            console.print("[bold green]GO! Booking window open.[/bold green]")

            if dry_run:
                console.print("[yellow]Dry run — testing direct URL navigation...[/yellow]")
                results_url = build_results_url(booking)
                await page.goto(results_url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle")
                await page.screenshot(path=f"dry_run_{booking.name}.png")
                console.print("[green]Results page loaded. Screenshot saved.[/green]")
                console.print("[green]Browser closing in 5 seconds...[/green]")
                await asyncio.sleep(5)
                return True

            from .booker import select_area_and_reserve, dismiss_cookie_consent

            console.print("[bold]Reloading results page...[/bold]")
            await page.reload(wait_until="domcontentloaded")
            await dismiss_cookie_consent(page)

            try:
                await select_area_and_reserve(page, booking.campsite, lambda m: console.print(f"  {m}"))
                console.print(
                    Panel("[bold green]ADDED TO CART![/bold green]\n"
                          "Complete checkout in the browser — you have ~15 min.",
                          border_style="green")
                )
                await page.screenshot(path=f"cart_success_{booking.name}.png")
                notify("Camping Bot", f"{booking.park} in cart! Checkout now!")
                await asyncio.sleep(900)
                return True
            except Exception as e:
                console.print(f"[red]Failed: {e}[/red]")
                console.print(Panel("[bold red]BOOKING FAILED[/bold red]", border_style="red"))
                await page.screenshot(path=f"booking_failed_{booking.name}.png")
                notify("Camping Bot", f"FAILED to add {booking.park} to cart")
                return False

        finally:
            await browser.close()


async def run_all(config_path: str, dry_run: bool = False):
    """Load config and run all bookings whose window opens today."""
    bookings = load_config(config_path)
    now = datetime.now()
    today = now.date()

    due_bookings = [
        b for b in bookings
        if b.booking_opens_at.date() == today
    ]

    if not due_bookings:
        console.print("[yellow]No bookings scheduled to open today.[/yellow]")
        console.print("Configured bookings:")
        for b in bookings:
            console.print(f"  - {b.name}: opens {b.booking_opens_at.strftime('%Y-%m-%d %H:%M')}")
        return

    console.print(f"[bold]Found {len(due_bookings)} booking(s) for today.[/bold]")

    results = {}
    for booking in due_bookings:
        success = await run_booking(booking, dry_run=dry_run)
        results[booking.name] = success

    console.print("\n[bold]Results:[/bold]")
    for name, success in results.items():
        status = "[green]SUCCESS[/green]" if success else "[red]FAILED[/red]"
        console.print(f"  {name}: {status}")


def main():
    config_path = "configs/booking.yaml"
    dry_run = False

    args = sys.argv[1:]
    for arg in args:
        if arg.startswith("--config="):
            config_path = arg.split("=", 1)[1]
        elif arg == "--dry-run":
            dry_run = True
        elif arg == "--force":
            pass
        elif not arg.startswith("-"):
            config_path = arg

    if "--force" in args:
        bookings = load_config(config_path)
        for booking in bookings:
            asyncio.run(run_booking(booking, dry_run=dry_run, force=True))
    else:
        asyncio.run(run_all(config_path, dry_run=dry_run))


if __name__ == "__main__":
    main()
