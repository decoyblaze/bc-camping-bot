"""Day-use pass booking logic for reserve.bcparks.ca/dayuse/.

Completely separate system from camping.bcparks.ca — no login required,
uses Cloudflare Turnstile instead. Booking window: 7 AM PT, 2 days before visit.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from playwright.async_api import Page

DAYUSE_URL = "https://reserve.bcparks.ca/dayuse/"
DAYUSE_API = "https://d757dzcblh.execute-api.ca-central-1.amazonaws.com/api"

DAYUSE_PARKS = {
    "Golden Ears": {
        "orcs": "0008",
        "type": "Parking",
        "facilities": [
            "Alouette Lake Boat Launch Parking",
            "Alouette Lake South Beach Day-Use Parking Lot",
            "Gold Creek Parking Lot",
            "West Canyon Trailhead Parking Lot",
        ],
    },
    "Joffre Lakes": {
        "orcs": "0363",
        "type": "Trail",
        "facilities": [
            "Joffre Lakes",
        ],
    },
    "Garibaldi": {
        "orcs": "0007",
        "type": "Parking",
        "facilities": [
            "Cheakamus",
            "Diamond Head",
            "Rubble Creek",
        ],
    },
    "Mount Seymour": {
        "orcs": "0015",
        "type": "Parking",
        "facilities": [
            "Mount Seymour",
        ],
    },
}


async def navigate_to_park(page: Page, park_name: str, log_fn=None) -> bool:
    """Navigate to the day-use landing page and click Book a Pass for the park."""
    _log = log_fn or (lambda x: None)

    await page.goto(DAYUSE_URL, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_selector("button.booking-button", timeout=15000)

    buttons = await page.query_selector_all("button.booking-button")
    park_data = DAYUSE_PARKS.get(park_name)
    if not park_data:
        _log(f"Unknown day-use park: {park_name}")
        return False

    for btn in buttons:
        card = await btn.evaluate_handle('el => el.closest(".card, .card-disabled")')
        text = await card.evaluate("el => el.innerText")
        if park_name in text:
            await btn.click()
            _log(f"Clicked Book a Pass for {park_name}")
            break
    else:
        _log(f"No Book a Pass button found for {park_name}")
        return False

    await page.wait_for_selector("#passType", timeout=15000)
    return True


async def fill_form(
    page: Page,
    visit_date: str,
    facility_name: str,
    time_slot: str = "DAY",
    num_passes: int = 1,
    log_fn=None,
) -> bool:
    """Fill the day-use booking form: date, pass type, booking time, pass count.

    Args:
        visit_date: YYYY-MM-DD format
        facility_name: exact facility name from DAYUSE_PARKS
        time_slot: "DAY", "AM", or "PM"
        num_passes: 1-4 for trail passes (ignored for parking)
    """
    _log = log_fn or (lambda x: None)

    await page.focus("#visitDate")
    await page.keyboard.press("Meta+A")
    await page.keyboard.press("Backspace")
    await page.keyboard.type(visit_date)
    await page.keyboard.press("Tab")
    await asyncio.sleep(0.5)
    _log(f"Visit date: {visit_date}")

    select = await page.query_selector("#passType")
    options = await select.query_selector_all("option")
    target_index = None
    for i, opt in enumerate(options):
        text = await opt.inner_text()
        if facility_name in text:
            target_index = i
            break

    if target_index is None:
        _log(f"Facility '{facility_name}' not found in pass type dropdown")
        return False

    await page.select_option("#passType", index=target_index)
    _log(f"Pass type: {facility_name}")
    await asyncio.sleep(2)

    radio_id = f"#visitTime{time_slot}"
    try:
        radio = await page.wait_for_selector(radio_id, timeout=8000)
        is_disabled = await radio.is_disabled()
        if is_disabled:
            _log(f"Time slot {time_slot} is disabled (not available)")
            return False
        await radio.click()
        _log(f"Booking time: {time_slot}")
    except Exception:
        _log(f"Time slot {time_slot} not found")
        return False

    await asyncio.sleep(0.3)

    pass_count_el = await page.query_selector("#passCount")
    if pass_count_el:
        await page.select_option("#passCount", str(num_passes))
        _log(f"Number of passes: {num_passes}")
        await asyncio.sleep(0.3)

    return True


async def wait_for_captcha_and_next(page: Page, log_fn=None, timeout: int = 300000) -> bool:
    """Wait for user to solve CAPTCHA, clicking Next repeatedly until it works.

    Clicks Next every second. Before the CAPTCHA is solved, Next does
    nothing. Once the user clicks the checkbox and it verifies, the
    next click goes through and the contact form loads.
    """
    _log = log_fn or (lambda x: None)
    t0 = time.monotonic()

    _log(">>> Click the CAPTCHA checkbox! <<<")

    while time.monotonic() - t0 < timeout / 1000:
        on_contact = await page.query_selector("#firstName")
        if on_contact:
            _log(f"Contact form loaded! ({time.monotonic() - t0:.1f}s)")
            return True

        try:
            next_btn = page.locator("button:has-text('Next'):not(:has-text('Back'))")
            if await next_btn.count() > 0 and await next_btn.is_enabled():
                await next_btn.click(timeout=2000)
        except Exception:
            pass

        await asyncio.sleep(1)

    _log(f"Timed out waiting for contact form ({time.monotonic() - t0:.0f}s)")
    return False


async def fill_contact_form(
    page: Page,
    first_name: str,
    last_name: str,
    email: str,
    phone: str = "",
    log_fn=None,
) -> bool:
    """Fill the contact info form that appears after Turnstile."""
    _log = log_fn or (lambda x: None)

    try:
        inputs = await page.evaluate("""() => {
            var result = {};
            var all = document.querySelectorAll('input[type="text"], input[type="email"], input:not([type])');
            for (var i = 0; i < all.length; i++) {
                var inp = all[i];
                var label = '';
                var lbl = inp.closest('.form-group, .mb-3, div');
                if (lbl) {
                    var l = lbl.querySelector('label');
                    if (l) label = l.textContent.trim().toLowerCase();
                }
                if (!label && inp.placeholder) label = inp.placeholder.toLowerCase();
                result[inp.id || ('input-' + i)] = label;
            }
            return result;
        }""")
        _log(f"Form fields: {inputs}")

        all_inputs = await page.query_selector_all("input[type='text'], input[type='email'], input:not([type])")
        for inp in all_inputs:
            label = await inp.evaluate("""el => {
                var div = el.closest('.form-group, .mb-3, div');
                if (div) { var l = div.querySelector('label'); if (l) return l.textContent.trim().toLowerCase(); }
                return (el.placeholder || '').toLowerCase();
            }""")
            if "first" in label:
                await inp.fill(first_name)
                _log(f"First name: {first_name}")
            elif "last" in label:
                await inp.fill(last_name)
                _log(f"Last name: {last_name}")
            elif "re-type" in label or "retype" in label or "confirm" in label:
                await inp.fill(email)
                _log(f"Confirm email: {email}")
            elif "email" in label:
                await inp.fill(email)
                _log(f"Email: {email}")

        agree_cb = await page.query_selector("input[type='checkbox'][id*='agree' i], input[type='checkbox'][id*='consent' i]")
        if not agree_cb:
            checkboxes = await page.query_selector_all("input[type='checkbox']")
            for cb in checkboxes:
                label = await cb.evaluate("""el => {
                    var div = el.closest('.form-group, .form-check, .mb-3, div');
                    return div ? div.textContent.trim().toLowerCase() : '';
                }""")
                if "read and agree" in label or "agree to" in label:
                    agree_cb = cb
                    break
        if agree_cb:
            await agree_cb.check()
            _log("Checked agreement checkbox")
        else:
            label_btn = page.locator("text=I have read and agree")
            try:
                await label_btn.click(timeout=3000)
                _log("Clicked agreement label")
            except Exception:
                _log("Warning: could not find agreement checkbox")

        return True
    except Exception as e:
        _log(f"Failed to fill contact form: {e}")
        return False


async def submit_booking(page: Page, log_fn=None) -> Optional[str]:
    """Click the submit button on the contact form.

    Returns the registration number if successful.
    """
    _log = log_fn or (lambda x: None)
    t0 = time.monotonic()

    submit_btn = page.locator("button:has-text('Submit')")
    try:
        await submit_btn.wait_for(state="visible", timeout=10000)
        await submit_btn.click()
        _log("Booking submitted!")
    except Exception:
        book_btn = page.locator("button:has-text('Book')")
        try:
            await book_btn.click(timeout=5000)
            _log("Booking submitted!")
        except Exception as e:
            _log(f"Could not find submit button: {e}")
            return None

    try:
        reg_el = await page.wait_for_selector(
            "app-registration-details, [id='registration']",
            timeout=30000,
        )
        _log(f"Booking confirmed! ({time.monotonic() - t0:.2f}s)")

        reg_num = await page.evaluate("""() => {
            var all = document.querySelectorAll('h3, h2, .registration-number, [class*="registration"]');
            for (var i = 0; i < all.length; i++) {
                var text = all[i].innerText.trim();
                if (text.match(/^[A-Z0-9]{6,}$/) || text.match(/\\d{6,}/)) return text;
            }
            var body = document.body.innerText;
            var match = body.match(/registration[^:]*:\\s*([A-Z0-9]{6,})/i);
            if (match) return match[1];
            match = body.match(/confirmation[^:]*:\\s*([A-Z0-9]{6,})/i);
            if (match) return match[1];
            return body.substring(0, 200);
        }""")
        if reg_num:
            _log(f"Registration number: {reg_num}")
        return reg_num
    except Exception:
        _log("Could not verify confirmation — check the browser")
        return None


async def check_availability(page: Page, log_fn=None) -> dict:
    """Read the current availability text from the booking time cards."""
    _log = log_fn or (lambda x: None)
    result = {}

    for slot in ["AM", "PM", "DAY"]:
        test_id = f"{slot.lower()}-availability-text"
        el = await page.query_selector(f"[data-testid='{test_id}']")
        if el:
            text = await el.inner_text()
            result[slot] = text.strip()

    return result
