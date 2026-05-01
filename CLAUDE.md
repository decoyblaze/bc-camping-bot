# BC Camping Bot

Automated booking bot for camping.bcparks.ca — supports both backcountry and frontcountry campsite reservations. Fires at exactly 7:00 AM PT when the booking window opens.

## How to run

```bash
./setup.sh       # one-time: creates venv, installs deps, installs Playwright browsers
.venv/bin/camping-bot   # launches the GUI app
```

CLI alternative: `.venv/bin/book --force`

## Architecture

- `bc_camping_bot/gui.py` — pywebview desktop app (HTML/CSS/JS frontend, Python `Api` class backend). This is the primary interface.
- `bc_camping_bot/booker.py` — Core booking logic: URL builder, area selection, checkout steps. All Playwright interactions live here. Contains both backcountry and frontcountry flows.
- `bc_camping_bot/runner.py` — CLI entry point (same logic as GUI, less maintained).
- `bc_camping_bot/timesync.py` — NTP sync for precise 7 AM execution.
- `bc_camping_bot/stealth.py` — Anti-detection measures (user agent, stealth JS). No viewport override — browser uses natural window size.
- `bc_camping_bot/config.py` — YAML config parser + `Booking` dataclass.
- `bc_camping_bot/notify.py` — macOS notifications.
- `bc_camping_bot/session.py` — Session save/load helpers.
- `configs/booking.yaml` — Booking configuration.

## Booking Types

### Backcountry
- Uses `PARK_IDS` dict (currently Garibaldi only)
- Flow: Search → "Available Areas" dropdown → "Add Area to stay" → "Reserve Area: ..." → Checkout
- `searchTabGroupId=3`, `bookingCategoryId=4`

### Frontcountry / Campsite
- Uses `FRONTCOUNTRY_PARKS` dict (13 Coastal Mainland parks)
- Flow: Search → click campsite marker on map → Reserve button in details panel → Checkout
- `searchTabGroupId=0`, `bookingCategoryId=0`
- GUI supports up to 5 fallback sites tried in priority order
- Equipment selection (1 Tent, 2 Tents, Van/Camper, etc.) done via page dropdown, not URL params

## Backcountry real run flow (GUI — Start Bot)

1. Warms session on camping.bcparks.ca homepage
2. Pre-navigates to results URL (caches all JS/CSS/API assets)
3. Pre-clicks Search to render "Build your stay" section + pre-selects campsite in dropdown
4. Waits for 7:00:00.000 PT (NTP-synced)
5. Clicks Search (refreshes availability — DOM already built, area already selected)
6. Clicks "Add Area to stay" → IN CART (~0.1-0.3s)
7. Clicks "Reserve Area: ..." → Reserved (~1.7s)
8. If Full Checkout: 6 automated checkout steps → payment page (~8s total)
9. Timer tracks each step duration

## Frontcountry real run flow

1. Warms session on camping.bcparks.ca homepage
2. Pre-navigates to area results URL (caches JS/CSS/map tiles)
3. Selects equipment from dropdown if not "1 Tent"
4. Pre-clicks Search to render map with campsite markers
5. Waits for 7:00:00.000 PT (NTP-synced)
6. Clicks Search (refreshes availability — map labels already in DOM)
7. Batch-finds all site SVG IDs in one `page.evaluate()` call (avoids slow per-site JS overhead)
8. For each site in priority list:
   a. Clicks marker's parent element using pre-found SVG ID
   b. Waits for Reserve button (`exact=True`, `state="attached"`) in details panel
   c. Scrolls into view and clicks Reserve
   d. If no Reserve button within 2s → site unavailable, try next
9. Retries up to 10 cycles (re-clicks Search each cycle)
10. If Full Checkout: same 6 checkout steps as backcountry

## Frontcountry map interaction — KEY DETAILS

- **Marker SVG IDs**: `resourceSvg[<resourceId>]` — each campsite marker has a unique SVG element
- **Label IDs**: `resourceSvg[<resourceId>]-label` — the text label next to each marker
- **Clicking the marker** opens a details panel on the right sidebar with site info
- **Reserve button** is OUTSIDE the `[role="complementary"]` region — it's a sibling, not a child. Use `page.get_by_role("button", name="Reserve", exact=True)` to avoid matching the legend's "Proceed to checkout to reserve"
- **Reserve button may be below the scroll fold** — use `scroll_into_view_if_needed()` before clicking
- **Availability classes**: `icon-available`, `icon-unavailable`, `icon-invalid` on the marker's parent `.leaflet-marker-icon.map-icon`
- **Equipment dropdown**: URL always loads with `equipmentId=-32768` (1 Tent). To use different equipment, select it from the page's combobox BEFORE clicking Search. Equipment IDs in the URL don't map 1:1 to dropdown values.
- **Don't wait for map labels after 7 AM Search** — they're already in the DOM from pre-load. Check if they exist, proceed immediately if so.

## Lessons from real 7 AM run (2026-04-25)

- **Pre-clicking "Add to stay" before 7 AM DOES NOT WORK.** The server rejects it — needs a fresh Search at 7 AM to load availability. Don't try to shortcut this.
- **Manual checkout is not viable at 7 AM.** The site is too slammed for pages to load. Use Full Checkout mode so the bot clicks through all 6 steps automatically.
- **Cart is tied to browser session, not account.** Can't checkout on a different device/browser. The bot must complete checkout in the same Playwright browser that added to cart.
- **The "Available Areas" dropdown NEVER appears without clicking Search first.** Always click Search — don't wait for it to appear on its own.
- **First real run took 8.44s to Add to stay, 13.31s total.** Server load at 7 AM is the bottleneck, not code speed.
- **Use Chrome profile, not saved session.** Freshest cookies, better anti-detection. Bot auto-closes Chrome, uses profile, reopens when done.
- **Test runs show 0.11–0.31s to cart** — code is optimized, server response is the variable.
- **Frontcountry test runs show 3.31–5.76s to Reserve** — includes map interaction + fallback sites. First site unavailable adds ~2-4s (marker click + Reserve timeout).

## Key technical details — READ THESE before making changes

### URL parameters
- `endDate` must be the departure date (startDate + nights). Previously we set endDate=startDate but BC Parks now renders 0 nights when they're equal.
- The `searchTime` param uses UTC format.
- `peopleCapacityCategoryCounts` is URL-encoded JSON array (backcountry only).
- Frontcountry uses `equipmentId` and `subEquipmentId` instead.

### Page behavior (backcountry)
- Navigating to the results URL does NOT show the "Available Areas" dropdown. You MUST click "Search for availability" first — this triggers the "Build your stay" section to render.
- After clicking "Add Area to stay", the form title changes from "Build your stay" to "Your stay", and the Reserve button changes from `"Reserve"` to `"Reserve Area: <campsite> <dates>"`. Use `re.compile(r"^Reserve Area:")` to match it.
- The legend section has a button called "Proceed to checkout to reserve" which matches `name="Reserve"` — never use an unscoped Reserve button selector for backcountry.
- Park Alerts dialog appears after Reserve and must be acknowledged.
- Cookie consent button may appear ("I Consent").

### Page behavior (frontcountry)
- Map view is the default. Site labels (`.map-site-label`) and marker SVGs render after Search.
- Clicking a marker opens a details panel on the right. For available sites, a green "Reserve" button appears at the bottom of the panel.
- The Reserve button is NOT inside `[role="complementary"]` — it's a sibling element below it.
- Use `exact=True` when matching the Reserve button to avoid the legend's "Proceed to checkout to reserve".
- List view shows "No Available Campsites" when all are booked. Map view always shows markers (just different colors).

### Speed principles
- NEVER use `networkidle` in the booking flow — it adds 2-5s per step. Use `domcontentloaded` only.
- NEVER reload or re-navigate the page on failure. Stay on the same page and retry by clicking Search.
- Pre-navigate to results URL before 7 AM to cache assets — but the actual Search must happen at 7 AM.
- `dismiss_dialogs` timeouts should be minimal (300ms).
- For frontcountry: don't wait for map labels after Search if they're already in the DOM. Use 2s Reserve button timeout to fail fast on unavailable sites.
- For frontcountry: batch-find all site SVG IDs in one `page.evaluate()` call — first evaluate is slow (~1.7s), subsequent are fast (~0.06s). One batch call eliminates per-site overhead.
- For frontcountry: only use `pre_clicked=True` fast-path when the pre-click actually succeeded (tracked by `site_pre_clicked` flag). Avoids wasting 2-3s on a non-existent Reserve button.
- Browser viewport: use `no_viewport=True` in all `launch_persistent_context` calls so the browser uses natural window size. Don't force a viewport — it causes the BC Parks site to render off-center.
- Don't click Search multiple times in rapid succession — it resets the map render each time.

### Login
- Default method: "Save separate login session" — uses `launch_persistent_context` with a dedicated browser profile dir under `~/.bc-camping-bot/browser-profiles/`. Session name defaults to "Test".
- Alternative: "Use my Chrome profile" — if Chrome is running, gracefully quits it (sessions flush to disk), uses the profile directly via `launch_persistent_context`, then reopens Chrome when done. All cookies/login intact.
- GUI has a "Chrome Profile" dropdown that auto-discovers profiles from `~/Library/Application Support/Google/Chrome/` and pre-selects the one with a signed-in Google account.
- Cart is tied to the browser session — if the browser closes, the cart is lost. The bot NEVER closes the browser after the booking flow starts.
- **The bot's #1 job is Reserve (frontcountry) / Add to stay (backcountry).** A human cannot do this fast enough at 7 AM. Retries up to 10 times.
- Everything after Reserve/Add (checkout) is best effort. If it fails, the bot keeps the browser open and the user finishes manually.
- Previously tried: CDP (Chrome blocks it on default data dir), profile-copy (session cookies are in-memory only), `/api/cart` verification (doesn't track UI-added bookings), direct HTTP API calls (removed 2026-04-26).

### Test Timer
- GUI has a "Test Timer" checkbox that sets the target to 1 minute from now instead of the real booking time. Use this for end-to-end testing without waiting for 7 AM.

## What NOT to do
- Don't pre-click "Add to stay" before 7 AM — server rejects it (confirmed 2026-04-25).
- Don't add multiple retry strategies that navigate to different URLs. One clean flow, retries via Search button clicks only.
- Don't add `networkidle` waits in the fast path.
- Don't use `page.goto()` at 7 AM — the page is already loaded from pre-navigate, just click Search.
- Don't match the backcountry Reserve button by exact name — it's dynamic. Use regex.
- Don't rely on manual checkout at 7 AM — site is too slow. Use Full Checkout mode.
- Don't put equipment IDs other than -32768 in the frontcountry URL — use the page dropdown instead.
- Don't scope the frontcountry Reserve button search to `[role="complementary"]` — the button is outside it.
- Don't click Search rapidly in a loop — each click resets the map render. Click once, wait for results.

## Dependencies
- playwright (browser automation)
- pywebview (desktop GUI)
- pyyaml (config)
- ntplib (time sync)
- rich (CLI formatting)

## Frontcountry Parks (in booker.py `FRONTCOUNTRY_PARKS`)
13 Coastal Mainland parks configured: Alice Lake, Birkenhead Lake, Chilliwack Lake, Cultus Lake, Golden Ears, Inland Lake, Nairn Falls, Porpoise Bay, Porteau Cove, Rolley Lake, Saltery Bay, Sasquatch, Silver Lake. Each has `transactionLocationId`, `resourceLocationId`, `mapId`, and `areas` dict mapping area names to child mapIds.

## Backcountry Parks (in booker.py `PARK_IDS`)
Currently only Garibaldi is configured. To add parks, add entries to `PARK_IDS` dict with `transactionLocationId`, `resourceLocationId`, and `mapId` from the BC Parks site.
