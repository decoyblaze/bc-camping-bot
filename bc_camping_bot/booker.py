"""Core booking logic — navigates camping.bcparks.ca and adds/books a backcountry campsite.

Speed strategy (sub-1-second from booking window open):
1. Pre-load the results page before 7:00 AM to cache all JS/CSS/assets
2. At exactly 7:00:00.000, reload the page — cached resources = fast load
3. Select area → "Add Area to stay" (cart mode stops here, checkout mode continues)
4. Form-based fallback if direct URL approach fails
"""

import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import Page

from .config import Booking
from .stealth import apply_stealth, get_stealth_config, human_delay

BOOKING_URL = "https://camping.bcparks.ca"

PARK_IDS = {
    "Garibaldi": {
        "transactionLocationId": -2147483602,
        "resourceLocationId": -2147483609,
        "mapId": -2147483578,
    },
}

BACKCOUNTRY_RESERVATION = {
    "searchTabGroupId": 3,
    "bookingCategoryId": 4,
    "peopleCapacityCategoryId": -32764,
}


def build_results_url(booking: Booking) -> str:
    """Build the direct results URL, skipping the search form entirely."""
    park = PARK_IDS.get(booking.park)
    if not park:
        raise ValueError(
            f"Unknown park '{booking.park}'. Known parks: {list(PARK_IDS.keys())}"
        )

    start = booking.arrival_date.isoformat()
    end = booking.departure_date.isoformat()
    nights = booking.num_nights
    people = booking.num_people
    pads = booking.num_tent_pads

    cap_id = BACKCOUNTRY_RESERVATION["peopleCapacityCategoryId"]
    people_param = quote(f"[[{cap_id},null,{people},null]]")

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000")

    params = (
        f"transactionLocationId={park['transactionLocationId']}"
        f"&resourceLocationId={park['resourceLocationId']}"
        f"&mapId={park['mapId']}"
        f"&searchTabGroupId={BACKCOUNTRY_RESERVATION['searchTabGroupId']}"
        f"&bookingCategoryId={BACKCOUNTRY_RESERVATION['bookingCategoryId']}"
        f"&startDate={start}"
        f"&endDate={end}"
        f"&nights={nights}"
        f"&isReserving=true"
        f"&peopleCapacityCategoryCounts={people_param}"
        f"&equipmentCapacity={pads}"
        f"&searchTime={now}"
        f"&flexibleSearch={quote('[false,false,null,1]')}"
    )

    return f"{BOOKING_URL}/create-booking/results?{params}"


async def load_session(context_factory, booking: Booking):
    """Create a browser context with a saved session."""
    session_path = Path(booking.session_file)
    if not session_path.is_absolute():
        session_path = Path(__file__).parent.parent / booking.session_file
    session_data = json.loads(session_path.read_text())

    config = get_stealth_config()
    context = await context_factory(
        storage_state=session_data["storage_state"],
        viewport=config["viewport"],
        user_agent=config["user_agent"],
        locale=config["locale"],
        timezone_id=config["timezone_id"],
    )
    return context


CHROME_USER_DATA = str(Path.home() / "Library/Application Support/Google/Chrome")
CDP_PORT = 9222


def is_chrome_running() -> bool:
    import subprocess
    try:
        result = subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True)
        return result.returncode == 0
    except Exception:
        return False


def _restart_chrome_with_cdp(profile: str = "Default", log=None):
    """Gracefully quit Chrome and relaunch with remote debugging enabled.

    Chrome restores all tabs automatically on relaunch.
    """
    import subprocess
    import time

    if log:
        log("Restarting Chrome with remote debugging...")

    subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to quit'],
                   capture_output=True, timeout=10)

    for _ in range(30):
        if not is_chrome_running():
            break
        time.sleep(0.2)

    chrome_app = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    subprocess.Popen(
        [chrome_app, f"--remote-debugging-port={CDP_PORT}",
         "--restore-last-session", f"--profile-directory={profile}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    for _ in range(50):
        try:
            import urllib.request
            urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1)
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("Chrome did not start with remote debugging in time")


def _chrome_has_cdp() -> bool:
    """Check if the running Chrome already has CDP enabled."""
    try:
        import urllib.request
        urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1)
        return True
    except Exception:
        return False


async def launch_with_chrome_profile(pw, profile: str = "Default", log=None):
    """Connect to the user's Chrome via CDP.

    If Chrome isn't running or doesn't have CDP: (re)launches Chrome with
    --remote-debugging-port, then connects. Chrome restores all tabs.

    Returns (context, page) tuple. The page is a new tab in the user's
    real Chrome session — fully logged in, all cookies intact.
    """
    if not is_chrome_running():
        import subprocess
        chrome_app = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        subprocess.Popen(
            [chrome_app, f"--remote-debugging-port={CDP_PORT}",
             f"--profile-directory={profile}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        import time
        for _ in range(50):
            try:
                import urllib.request
                urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1)
                break
            except Exception:
                time.sleep(0.2)
    elif not _chrome_has_cdp():
        _restart_chrome_with_cdp(profile, log=log)

    browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
    context = browser.contexts[0]
    page = await context.new_page()
    return context, page


async def dismiss_cookie_consent(page: Page):
    """Click the cookie consent button if it appears."""
    try:
        btn = page.get_by_role("button", name="I Consent")
        if await btn.is_visible(timeout=500):
            await btn.click()
    except Exception:
        pass


async def wait_through_queue(page: Page, log_fn=None, max_wait: int = 300) -> bool:
    """Detect and wait through Queue-IT virtual waiting room.

    Queue-IT redirects to a queue-it.net URL with a progress bar.
    When your turn comes, it redirects back to camping.bcparks.ca.
    Returns True if we got through (or no queue was present).
    """
    import time
    start = time.time()

    while time.time() - start < max_wait:
        url = page.url
        if "queue-it.net" in url or "queue.camping.bcparks.ca" in url:
            if log_fn:
                elapsed = int(time.time() - start)
                log_fn(f"In Queue-IT waiting room... ({elapsed}s)")

            # Check for "your turn" or redirect back to main site
            try:
                await page.wait_for_url("**/camping.bcparks.ca/**", timeout=10000)
                if log_fn:
                    log_fn("Through the queue!")
                return True
            except Exception:
                pass

            await asyncio.sleep(2)
        else:
            return True

    if log_fn:
        log_fn(f"Queue-IT wait exceeded {max_wait}s")
    return False


async def dismiss_dialogs(page: Page, log_fn=None):
    """Dismiss any popup dialogs — Park Alerts, reset search confirmation, etc."""
    dialog_handlers = [
        ("Park Alerts", "Acknowledge"),
        ("Are you sure you want to reset your search?", "Confirm"),
    ]
    for dialog_name, button_name in dialog_handlers:
        try:
            dialog = page.get_by_role("dialog", name=dialog_name)
            if await dialog.is_visible(timeout=300):
                btn = dialog.get_by_role("button", name=button_name)
                await btn.click()
                if log_fn:
                    log_fn(f"Dismissed '{dialog_name}'")
        except Exception:
            pass


async def click_search_button(page: Page, log_fn=None):
    """Click the green 'Search for availability' button to force results to load."""
    _log = log_fn or (lambda x: None)
    _log("Clicking Search...")
    search_btn = page.get_by_role("button", name="Search for availability")
    await search_btn.click()


async def add_to_cart(page: Page, campsite: str, log_fn=None) -> bool:
    """Search → select area → Add to stay. Gets the item into the cart as fast as possible.

    If the dropdown isn't visible, clicks Search to force it to load.
    Retries Search up to 3 times — never reloads the page.
    """
    _log = log_fn or (lambda x: None)

    combo = page.get_by_role("combobox", name="Available Areas")

    if not await combo.is_visible():
        for search_attempt in range(3):
            try:
                await click_search_button(page, _log)
                await combo.wait_for(state="visible", timeout=10000)
                break
            except Exception:
                if search_attempt == 2:
                    raise Exception("Available Areas dropdown never appeared after 3 Search clicks")

    await combo.click()

    if campsite.lower() == "any":
        first_option = page.get_by_role("option").first
        await first_option.click(timeout=15000)
    else:
        option = page.get_by_role("option", name=campsite)
        await option.click(timeout=15000)

    add_btn = page.get_by_role("button", name="Add Area to stay")
    await add_btn.click()
    _log("Added to stay!")
    return True


async def select_area_and_reserve(page: Page, campsite: str, log_fn=None) -> bool:
    """Search → select area → Add to stay → Reserve. Full flow for backwards compat."""
    import re as _re
    _log = log_fn or (lambda x: None)

    await add_to_cart(page, campsite, log_fn)

    reserve_btn = page.get_by_role("button", name=_re.compile(r"^Reserve Area:"))
    await reserve_btn.wait_for(state="visible", timeout=10000)
    await reserve_btn.click()
    await dismiss_dialogs(page, log_fn)
    _log("Reserved!")
    return True


async def complete_checkout(page: Page, log_fn=None) -> bool:
    """Full multi-step checkout: Reserve → Acknowledge → Confirm → Payment page.

    Steps after Reserve:
    1. /reservationmessages — check "All reservation details are correct." → Confirm
    2. /cart — "Proceed to checkout"
    3. /reviewpolicies — check both policy checkboxes → "Confirm acknowledgements"
    4. /contactinfo — "Confirm account details"
    5. /permitholder — "I will be the occupant." (pre-selected) → "Confirm occupant"
    6. /partyinfo — "Confirm party information"
    7. Payment page — STOP (user enters payment manually)
    """
    import time as _time
    _log = log_fn or (lambda x: None)
    t0 = _time.monotonic()
    T = 10000

    # Step 1: check box and confirm reservation details
    checkbox = page.get_by_role("checkbox", name="All reservation details are correct.")
    await checkbox.wait_for(state="visible", timeout=T)
    await checkbox.check(force=True)
    await page.get_by_role("button", name="Confirm reservation details").click()
    _log(f"1/6 Reservation confirmed ({_time.monotonic() - t0:.2f}s)")

    # Step 2: proceed to checkout
    proceed_btn = page.get_by_role("button", name="Proceed to checkout")
    await proceed_btn.wait_for(state="visible", timeout=T)
    await proceed_btn.click()
    _log(f"2/6 Proceed to checkout ({_time.monotonic() - t0:.2f}s)")

    # Step 3: check both policy boxes and confirm
    rules_cb = page.get_by_role("checkbox", name="EVERYONE IN MY GROUP WILL FOLLOW ALL PARK RULES")
    await rules_cb.wait_for(state="visible", timeout=T)
    await rules_cb.check(force=True)
    liability_cb = page.get_by_role("checkbox", name="I have read and agree to the Exclusion of Liability Notice.")
    await liability_cb.check(force=True)
    await page.get_by_role("button", name="Confirm acknowledgements").click()
    _log(f"3/6 Policies accepted ({_time.monotonic() - t0:.2f}s)")

    # Step 4: confirm account
    account_btn = page.get_by_role("button", name="Confirm account details")
    await account_btn.wait_for(state="visible", timeout=T)
    await account_btn.click()
    _log(f"4/6 Account confirmed ({_time.monotonic() - t0:.2f}s)")

    # Step 5: confirm occupant
    occupant_btn = page.get_by_role("button", name="Confirm occupant")
    await occupant_btn.wait_for(state="visible", timeout=T)
    await occupant_btn.click()
    _log(f"5/6 Occupant confirmed ({_time.monotonic() - t0:.2f}s)")

    # Step 6: confirm party
    party_btn = page.get_by_role("button", name="Confirm party information")
    await party_btn.wait_for(state="visible", timeout=T)
    await party_btn.click()
    _log(f"6/6 Party confirmed ({_time.monotonic() - t0:.2f}s)")

    _log(f"Payment page reached. (checkout: {_time.monotonic() - t0:.2f}s)")
    return True


async def pre_navigate(page: Page, booking: Booking, log_fn=None):
    """Pre-load the results page to cache JS/CSS/images before the booking window opens."""
    results_url = build_results_url(booking)
    await page.goto(results_url, wait_until="domcontentloaded")
    await wait_through_queue(page, log_fn)
    await page.wait_for_load_state("networkidle")


async def pre_select_area(page: Page, campsite: str, log_fn=None):
    """During pre-navigate phase: click Search, render Build your stay, select the area.

    At 7 AM all we need is a single click on 'Add Area to stay'.
    """
    _log = log_fn or (lambda x: None)

    combo = page.get_by_role("combobox", name="Available Areas")

    if not await combo.is_visible():
        _log("Pre-clicking Search to render Build your stay...")
        search_btn = page.get_by_role("button", name="Search for availability")
        await search_btn.click()
        await combo.wait_for(state="visible", timeout=15000)

    # Wait for options to populate (availability API must respond first)
    await combo.click()
    if campsite.lower() == "any":
        first_option = page.get_by_role("option").first
        await first_option.wait_for(state="visible", timeout=15000)
        await first_option.click()
    else:
        option = page.get_by_role("option", name=campsite)
        try:
            await option.wait_for(state="visible", timeout=15000)
            await option.click()
        except Exception:
            all_options = page.get_by_role("option")
            count = await all_options.count()
            names = []
            for i in range(count):
                names.append(await all_options.nth(i).inner_text())
            _log(f"Available options ({count}): {names}")
            raise
    _log(f"Pre-selected: {campsite}. Ready to fire at 7 AM.")


async def attempt_booking(page: Page, booking: Booking, full_checkout: bool = False, log_fn=None) -> bool:
    """Fast path: navigate to results URL (list view) → click area → Reserve.

    If full_checkout=True, continues through the full checkout flow.
    Handles Queue-IT waiting room and popup dialogs.
    """
    await dismiss_cookie_consent(page)

    results_url = build_results_url(booking)
    await page.goto(results_url, wait_until="domcontentloaded")

    if not await wait_through_queue(page, log_fn):
        return False

    reserved = await select_area_and_reserve(page, booking.campsite, log_fn)
    if not reserved:
        return False

    if full_checkout:
        return await complete_checkout(page, log_fn)

    return True


async def attempt_booking_reload(page: Page, booking: Booking, full_checkout: bool = False, log_fn=None) -> bool:
    """Ultra-fast retry: reload the current results page, then click area → Reserve."""
    await page.reload(wait_until="domcontentloaded")

    if not await wait_through_queue(page, log_fn):
        return False

    reserved = await select_area_and_reserve(page, booking.campsite, log_fn)
    if not reserved:
        return False

    if full_checkout:
        return await complete_checkout(page, log_fn)

    return True


# ── Fallback: form-based flow if direct URL fails ────────────

async def attempt_booking_form(page: Page, booking: Booking, full_checkout: bool = False, log_fn=None) -> bool:
    """Slower fallback: fill the search form manually, then add to cart."""
    await apply_stealth(page)
    await page.goto(BOOKING_URL, wait_until="domcontentloaded")

    if not await wait_through_queue(page, log_fn):
        return False

    await page.wait_for_load_state("networkidle")
    await dismiss_cookie_consent(page)

    tab = page.get_by_role("tab", name="Backcountry")
    await tab.click(timeout=10000)
    await human_delay(200, 400)

    combo = page.get_by_role("combobox", name="Select park")
    await combo.click()
    await human_delay(100, 200)
    option = page.get_by_role("option", name=booking.park)
    await option.click(timeout=5000)
    await human_delay(100, 200)

    date_input = page.get_by_role("textbox", name="Arrival date")
    await date_input.click()
    await human_delay(100, 200)

    target_label = booking.arrival_date.strftime("%B %-d, %Y")
    for _ in range(12):
        try:
            day_btn = page.get_by_role("button", name=target_label)
            if await day_btn.is_visible(timeout=500):
                await day_btn.click()
                break
        except Exception:
            pass
        try:
            next_btn = page.get_by_role("button", name="View next month")
            await next_btn.click()
            await human_delay(80, 150)
        except Exception:
            break

    add_party = page.locator("#party-size-field-wrapper").get_by_role("button", name="Add one")
    for _ in range(booking.num_people - 1):
        await add_party.click()
        await human_delay(30, 80)

    add_pads = page.locator("#equipment-capacity-field-wrapper").get_by_role("button", name="Add one")
    for _ in range(booking.num_tent_pads - 1):
        await add_pads.click()
        await human_delay(30, 80)

    search_btn = page.get_by_role("button", name="Search for availability")
    await search_btn.click()
    await page.wait_for_load_state("domcontentloaded")
    await human_delay(500, 1000)

    await dismiss_dialogs(page, log_fn)
    reserved = await select_area_and_reserve(page, booking.campsite, log_fn)
    if not reserved:
        return False

    if full_checkout:
        return await complete_checkout(page, log_fn)

    return True
