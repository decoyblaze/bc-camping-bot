"""Session saver — log in manually, save cookies for the bot to reuse."""

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright
from rich.console import Console

from .stealth import apply_stealth, get_stealth_config

console = Console()
DISCOVER_CAMPING_URL = "https://camping.bcparks.ca"
SESSIONS_DIR = Path(__file__).parent.parent / "sessions"


async def save_session(output_file: str):
    SESSIONS_DIR.mkdir(exist_ok=True)
    output_path = SESSIONS_DIR / output_file

    config = get_stealth_config()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport=config["viewport"],
            user_agent=config["user_agent"],
            locale=config["locale"],
            timezone_id=config["timezone_id"],
        )
        page = await context.new_page()
        await apply_stealth(page)

        console.print(f"\n[bold blue]Opening {DISCOVER_CAMPING_URL}...[/bold blue]")
        await page.goto(DISCOVER_CAMPING_URL)

        console.print(
            "\n[bold yellow]Please log in manually in the browser window.[/bold yellow]"
        )
        console.print("[yellow]Once you're fully logged in, press Enter here...[/yellow]")

        await asyncio.get_event_loop().run_in_executor(None, input)

        cookies = await context.cookies()
        storage = await context.storage_state()

        session_data = {
            "cookies": cookies,
            "storage_state": storage,
        }
        output_path.write_text(json.dumps(session_data, indent=2))
        console.print(f"\n[bold green]Session saved to {output_path}[/bold green]")

        await browser.close()


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "default.json"
    if not name.endswith(".json"):
        name += ".json"
    asyncio.run(save_session(name))


if __name__ == "__main__":
    main()
