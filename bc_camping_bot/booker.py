"""Core booking logic — navigates camping.bcparks.ca and adds/books a backcountry campsite.

Speed strategy (sub-1-second from booking window open):
1. Pre-load the results page before 7:00 AM to cache all JS/CSS/assets
2. At exactly 7:00:00.000, reload the page — cached resources = fast load
3. Select area → "Add Area to stay" (cart mode stops here, checkout mode continues)
4. Form-based fallback if direct URL approach fails
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional
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

FRONTCOUNTRY_PARKS = {
    "Alice Lake": {
        "transactionLocationId": -2147483647,
        "resourceLocationId": -2147483647,
        "mapId": -2147483648,
        "areas": {
            "A (Sites 1-55)": -2147483647,
            "B (Sites 56-96)": -2147483646,
            "Walk-In": -2147483645,
        },
    },
    "Birkenhead Lake": {
        "transactionLocationId": -2147483639,
        "resourceLocationId": -2147483640,
        "mapId": -2147483631,
        "areas": {},
    },
    "Chilliwack Lake": {
        "transactionLocationId": -2147483621,
        "resourceLocationId": -2147483627,
        "mapId": -2147483619,
        "areas": {
            "Greendrop Loop": -2147483618,
            "Lindeman Loop": -2147483617,
            "Paleface Loop": -2147483616,
            "Radium Loop": -2147483615,
            "Flora Loop": -2147483614,
        },
    },
    "Cultus Lake": {
        "transactionLocationId": -2147483617,
        "resourceLocationId": -2147483623,
        "mapId": -2147483610,
        "areas": {
            "Entrance Bay": -2147483609,
            "Clear Creek": -2147483608,
            "Delta Grove": -2147483607,
            "Maple Bay": -2147483606,
        },
    },
    "Golden Ears": {
        "transactionLocationId": -2147483599,
        "resourceLocationId": -2147483606,
        "mapId": -2147483576,
        "areas": {
            "Alouette North": -2147483575,
            "Alouette South": -2147483574,
            "Gold Creek": -2147483573,
            "North Beach": -2147483572,
        },
    },
    "Inland Lake": {
        "transactionLocationId": -2147483591,
        "resourceLocationId": -2147483599,
        "mapId": -2147483554,
        "areas": {
            "Campground": -2147483553,
        },
    },
    "Nairn Falls": {
        "transactionLocationId": -2147483544,
        "resourceLocationId": -2147483564,
        "mapId": -2147483471,
        "areas": {},
    },
    "Porpoise Bay": {
        "transactionLocationId": -2147483517,
        "resourceLocationId": -2147483551,
        "mapId": -2147483452,
        "areas": {
            "Campground": -2147483451,
        },
    },
    "Porteau Cove": {
        "transactionLocationId": -2147483516,
        "resourceLocationId": -2147483550,
        "mapId": -2147483449,
        "areas": {
            "A (Sites 1-37)": -2147483448,
            "B (Sites 38-44)": -2147483447,
            "WalkIn (W1-W16)": -2147483446,
        },
    },
    "Rolley Lake": {
        "transactionLocationId": -2147483509,
        "resourceLocationId": -2147483543,
        "mapId": -2147483430,
        "areas": {
            "Campground": -2147483429,
            "Walk-in": -2147483251,
        },
    },
    "Saltery Bay": {
        "transactionLocationId": -2147483506,
        "resourceLocationId": -2147483540,
        "mapId": -2147483422,
        "areas": {
            "Campground": -2147483421,
        },
    },
    "Sasquatch": {
        "transactionLocationId": -2147483505,
        "resourceLocationId": -2147483539,
        "mapId": -2147483420,
        "areas": {
            "Hicks Campground": -2147483419,
            "Bench Campground": -2147483418,
            "Lakeside Campground": -2147483417,
        },
    },
    "Silver Lake": {
        "transactionLocationId": -2147483501,
        "resourceLocationId": -2147483535,
        "mapId": -2147483410,
        "areas": {},
    },
}

FRONTCOUNTRY_RESERVATION = {
    "searchTabGroupId": 0,
    "bookingCategoryId": 0,
    "equipmentId": -32768,
    "subEquipmentId": -32768,
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


def build_frontcountry_url(booking: Booking, area_map_id: int) -> str:
    """Build the direct results URL for a frontcountry campsite area."""
    park = FRONTCOUNTRY_PARKS.get(booking.park)
    if not park:
        raise ValueError(
            f"Unknown frontcountry park '{booking.park}'. "
            f"Known: {list(FRONTCOUNTRY_PARKS.keys())}"
        )

    start = booking.arrival_date.isoformat()
    end = booking.departure_date.isoformat()
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000")
    fc = FRONTCOUNTRY_RESERVATION

    params = (
        f"transactionLocationId={park['transactionLocationId']}"
        f"&resourceLocationId={park['resourceLocationId']}"
        f"&mapId={area_map_id}"
        f"&searchTabGroupId={fc['searchTabGroupId']}"
        f"&bookingCategoryId={fc['bookingCategoryId']}"
        f"&startDate={start}"
        f"&endDate={end}"
        f"&nights={booking.num_nights}"
        f"&isReserving=true"
        f"&equipmentId={fc['equipmentId']}"
        f"&subEquipmentId={fc['subEquipmentId']}"
        f"&searchTime={now}"
        f"&flexibleSearch={quote('[false,false,null,1]')}"
    )
    return f"{BOOKING_URL}/create-booking/results?{params}"


async def select_equipment(page: Page, equipment_label: str, log_fn=None):
    """Select equipment type from the page's Equipment dropdown.

    The URL always loads with '1 Tent' selected. This function changes it
    to the user's selection before Search is clicked.
    """
    import re as _re
    _log = log_fn or (lambda x: None)
    combo = page.get_by_role("combobox", name=_re.compile(
        r"(Tent|Van|Camper|Trailer|RV)", _re.IGNORECASE
    ))
    try:
        await combo.click(timeout=5000)
        option = page.get_by_role("option", name=equipment_label)
        await option.click(timeout=3000)
        _log(f"Equipment set to {equipment_label}")
    except Exception:
        _log(f"Could not change equipment to {equipment_label}")


async def frontcountry_find_sites(page: Page, site_names: list[str]) -> dict[str, str]:
    """Batch-find SVG IDs for all sites in one evaluate call.

    Returns {site_name: svg_id} for sites found on the map.
    Handles area prefixes: "A41" matches label "41" and vice versa.
    """
    return await page.evaluate("""(siteNames) => {
        const map = {};
        const labels = document.querySelectorAll('.map-site-label');
        for (const name of siteNames) {
            const target = name.trim().toUpperCase();
            const numOnly = target.replace(/^[A-Z]+[-\\s]?/, '');
            for (const lbl of labels) {
                const child = lbl.querySelector('[id$="-label"]');
                if (!child) continue;
                const text = child.textContent.trim().toUpperCase();
                if (text === target || text === numOnly || target === text.replace(/^[A-Z]+[-\\s]?/, '')) {
                    map[name] = child.id.replace('-label', '');
                    break;
                }
            }
        }
        return map;
    }""", site_names)


async def frontcountry_click_site(page: Page, site_name: str, log_fn=None, svg_id: str = None) -> bool:
    """Click a campsite marker on the map to open its details panel."""
    _log = log_fn or (lambda x: None)

    if not svg_id:
        result = await frontcountry_find_sites(page, [site_name])
        svg_id = result.get(site_name)

    if not svg_id:
        _log(f"Site {site_name} not found on map")
        return False

    marker = page.locator(f'[id="{svg_id}"]').locator('..')
    await marker.click()
    _log(f"Clicked site {site_name}")
    return True


async def frontcountry_reserve_site(
    page: Page, site_name: str, log_fn=None, timeout: int = 2000, svg_id: str = None
) -> bool:
    """Click a campsite marker, then click Reserve in the details panel."""
    import time as _time
    _log = log_fn or (lambda x: None)

    t0 = _time.monotonic()
    if not await frontcountry_click_site(page, site_name, _log, svg_id=svg_id):
        return False
    _log(f"  details panel opening... ({_time.monotonic() - t0:.2f}s)")

    reserve_btn = page.get_by_role("button", name="Reserve", exact=True)
    try:
        await reserve_btn.wait_for(state="attached", timeout=timeout)
        await reserve_btn.scroll_into_view_if_needed()
        await reserve_btn.click()
        _log(f"  Reserve clicked for {site_name}! ({_time.monotonic() - t0:.2f}s)")
        return True
    except Exception:
        _log(f"  no Reserve button for {site_name} ({_time.monotonic() - t0:.2f}s)")
        return False


async def frontcountry_add_to_cart(
    page: Page,
    booking: Booking,
    area_map_id: int,
    sites: list[str],
    log_fn=None,
    pre_clicked: bool = False,
) -> Optional[str]:
    """Try to reserve a frontcountry campsite from a priority-ordered list.

    Pre-condition: page is already on the area results URL with assets cached.
    At 7 AM: clicks Search to refresh availability, then tries each site in order.

    Returns the site name that was reserved, or None if all failed.
    """
    import time as _time
    _log = log_fn or (lambda x: None)

    t0 = _time.monotonic()
    try:
        await click_search_button(page, _log)
        _log(f"  Search clicked ({_time.monotonic() - t0:.2f}s)")
    except Exception:
        _log(f"  Search button not clickable ({_time.monotonic() - t0:.2f}s)")
        return None

    labels_exist = await page.query_selector('.map-site-label')
    if not labels_exist:
        try:
            await page.wait_for_selector('.map-site-label', timeout=15000)
        except Exception:
            _log(f"  Map labels never appeared ({_time.monotonic() - t0:.2f}s)")
            return None
    _log(f"  Map ready ({_time.monotonic() - t0:.2f}s)")

    site_ids = await frontcountry_find_sites(page, sites)
    if not site_ids and labels_exist:
        import asyncio as _asyncio
        await _asyncio.sleep(2)
        site_ids = await frontcountry_find_sites(page, sites)
    if not site_ids:
        sample = await page.evaluate("""() => {
            var labels = document.querySelectorAll('.map-site-label');
            var texts = [];
            for (var i = 0; i < Math.min(labels.length, 8); i++) {
                var child = labels[i].querySelector('[id$="-label"]');
                if (child) texts.push(child.textContent.trim());
            }
            return texts;
        }""")
        _log(f"  Map label samples: {sample}")
    _log(f"  Found {len(site_ids)}/{len(sites)} sites ({_time.monotonic() - t0:.2f}s)")

    for i, site in enumerate(sites):
        _log(f"Trying site {site}... ({_time.monotonic() - t0:.2f}s)")
        if i == 0 and pre_clicked:
            reserve_btn = page.get_by_role("button", name="Reserve", exact=True)
            try:
                await reserve_btn.wait_for(state="attached", timeout=2000)
                await reserve_btn.scroll_into_view_if_needed()
                await reserve_btn.click()
                _log(f"  Reserve clicked for {site}! ({_time.monotonic() - t0:.2f}s)")
                _log(f"RESERVED {site}! ({_time.monotonic() - t0:.2f}s)")
                return site
            except Exception:
                _log(f"  fast-path Reserve failed for {site} ({_time.monotonic() - t0:.2f}s)")
        svg_id = site_ids.get(site)
        if not svg_id:
            _log(f"  {site} not found on map ({_time.monotonic() - t0:.2f}s)")
            continue
        if await frontcountry_reserve_site(page, site, _log, svg_id=svg_id):
            _log(f"RESERVED {site}! ({_time.monotonic() - t0:.2f}s)")
            return site

    _log(f"All {len(sites)} sites failed ({_time.monotonic() - t0:.2f}s)")
    return None


async def load_session(context_factory, booking: Booking):
    """Create a browser context with a saved session."""
    session_path = Path(booking.session_file)
    if not session_path.is_absolute():
        session_path = Path(__file__).parent.parent / booking.session_file
    session_data = json.loads(session_path.read_text())

    config = get_stealth_config()
    context = await context_factory(
        storage_state=session_data["storage_state"],
        no_viewport=True,
        user_agent=config["user_agent"],
        locale=config["locale"],
        timezone_id=config["timezone_id"],
    )
    return context


from .platform_utils import (
    chrome_user_data_dir,
    is_chrome_running,
    quit_chrome,
    reopen_chrome,
)

CHROME_USER_DATA = str(chrome_user_data_dir())


async def launch_with_chrome_profile(pw, profile: str = "Default", log=None):
    """Launch Playwright using the user's Chrome profile directly.

    If Chrome is running, gracefully quits it first (sessions flush to disk).
    Uses launch_persistent_context on the real profile so all cookies/login
    are intact. Call reopen_chrome() when done.

    Returns (context, page) tuple.
    """
    if is_chrome_running():
        quit_chrome(log=log)

    config = get_stealth_config()
    context = await pw.chromium.launch_persistent_context(
        user_data_dir=CHROME_USER_DATA,
        channel="chrome",
        headless=False,
        no_viewport=True,
        locale=config["locale"],
        timezone_id=config["timezone_id"],
        args=[f"--profile-directory={profile}"],
    )
    page = context.pages[0] if context.pages else await context.new_page()
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


async def complete_checkout(page: Page, log_fn=None, frontcountry: bool = False) -> bool:
    """Full multi-step checkout to payment page.

    Backcountry steps (after "Reserve Area: ..."):
    1. /reservationmessages — check "All reservation details are correct." → Confirm
    2. /cart — "Proceed to checkout"
    3–6. policies, account, occupant, party → Payment

    Frontcountry steps (after Reserve on map):
    1. Navigate to cart (page is still on map after Reserve)
    2. /cart — "Proceed to checkout"
    3–6. Same as backcountry
    """
    import time as _time
    _log = log_fn or (lambda x: None)
    t0 = _time.monotonic()
    T = 45000

    if frontcountry:
        _log("Navigating to cart...")
        cart_url = f"{BOOKING_URL}/create-booking/cart"
        await page.goto(cart_url, wait_until="domcontentloaded", timeout=T)
        _log(f"1/6 Cart loaded ({_time.monotonic() - t0:.2f}s)")
    else:
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

    from .platform_utils import format_day
    target_label = format_day(booking.arrival_date, "%B %-d, %Y")
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
