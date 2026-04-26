# BC Camping Bot

Automated booking bot for camping.bcparks.ca backcountry campsites. Fires at exactly 7:00 AM PT when the booking window opens.

## How to run

```bash
./setup.sh       # one-time: creates venv, installs deps, installs Playwright browsers
.venv/bin/camping-bot   # launches the GUI app
```

CLI alternative: `.venv/bin/book --force`

## Architecture

- `bc_camping_bot/gui.py` — pywebview desktop app (HTML/CSS/JS frontend, Python `Api` class backend). This is the primary interface.
- `bc_camping_bot/booker.py` — Core booking logic: URL builder, area selection, checkout steps. All Playwright interactions live here.
- `bc_camping_bot/runner.py` — CLI entry point (same logic as GUI, less maintained).
- `bc_camping_bot/timesync.py` — NTP sync for precise 7 AM execution.
- `bc_camping_bot/stealth.py` — Anti-detection measures (user agent, viewport, etc).
- `bc_camping_bot/config.py` — YAML config parser + `Booking` dataclass.
- `bc_camping_bot/notify.py` — macOS notifications.
- `bc_camping_bot/session.py` — Session save/load helpers.
- `configs/booking.yaml` — Booking configuration.

## Real run flow (GUI — Start Bot)

1. Warms session on camping.bcparks.ca homepage
2. Pre-navigates to results URL (caches all JS/CSS/API assets)
3. Pre-clicks Search to render "Build your stay" section + pre-selects campsite in dropdown
4. Waits for 7:00:00.000 PT (NTP-synced)
5. Clicks Search (refreshes availability — DOM already built, area already selected)
6. Clicks "Add Area to stay" → IN CART (~0.1-0.3s)
7. Clicks "Reserve Area: ..." → Reserved (~1.7s)
8. If Full Checkout: 6 automated checkout steps → payment page (~8s total)
9. Timer tracks each step duration

## Lessons from real 7 AM run (2026-04-25)

- **Pre-clicking "Add to stay" before 7 AM DOES NOT WORK.** The server rejects it — needs a fresh Search at 7 AM to load availability. Don't try to shortcut this.
- **Manual checkout is not viable at 7 AM.** The site is too slammed for pages to load. Use Full Checkout mode so the bot clicks through all 6 steps automatically.
- **Cart is tied to browser session, not account.** Can't checkout on a different device/browser. The bot must complete checkout in the same Playwright browser that added to cart.
- **The "Available Areas" dropdown NEVER appears without clicking Search first.** Always click Search — don't wait for it to appear on its own.
- **First real run took 8.44s to Add to stay, 13.31s total.** Server load at 7 AM is the bottleneck, not code speed.
- **Use Chrome profile, not saved session.** Freshest cookies, better anti-detection. Bot connects to Chrome via CDP — no need to close Chrome.
- **Test runs show 0.11–0.31s to cart** — code is optimized, server response is the variable.

## Key technical details — READ THESE before making changes

### URL parameters
- `endDate` must be the departure date (startDate + nights). Previously we set endDate=startDate but BC Parks now renders 0 nights when they're equal.
- The `searchTime` param uses UTC format.
- `peopleCapacityCategoryCounts` is URL-encoded JSON array.

### Page behavior
- Navigating to the results URL does NOT show the "Available Areas" dropdown. You MUST click "Search for availability" first — this triggers the "Build your stay" section to render.
- After clicking "Add Area to stay", the form title changes from "Build your stay" to "Your stay", and the Reserve button changes from `"Reserve"` to `"Reserve Area: <campsite> <dates>"`. Use `re.compile(r"^Reserve Area:")` to match it.
- The legend section has a button called "Proceed to checkout to reserve" which matches `name="Reserve"` — never use an unscoped Reserve button selector.
- Park Alerts dialog appears after Reserve and must be acknowledged.
- Cookie consent button may appear ("I Consent").

### Speed principles
- NEVER use `networkidle` in the booking flow — it adds 2-5s per step. Use `domcontentloaded` only.
- NEVER reload or re-navigate the page on failure. Stay on the same page and retry by clicking Search.
- Pre-navigate to results URL before 7 AM to cache assets — but the actual Search must happen at 7 AM.
- `dismiss_dialogs` timeouts should be minimal (300ms).

### Login
- Default method: "Use my Chrome profile" — connects to Chrome via CDP (Chrome DevTools Protocol). If Chrome isn't running, launches it with `--remote-debugging-port=9222`. If Chrome is running without CDP, gracefully restarts it with the flag (tabs auto-restore). Opens a new tab in the user's real Chrome session — fully logged in, all cookies intact.
- GUI has a "Chrome Profile" dropdown that auto-discovers profiles from `~/Library/Application Support/Google/Chrome/` and pre-selects the one with a signed-in Google account.
- Alternative: "Save separate login session" — opens browser, user logs in, saves cookies/storage state to JSON.
- The profile-copy approach (copying Chrome profile to temp dir) was tried and abandoned — Chrome keeps session cookies in memory while running, so the copy is always missing the active login.

### Test Timer
- GUI has a "Test Timer" checkbox that sets the target to 1 minute from now instead of the real booking time. Use this for end-to-end testing without waiting for 7 AM.

## What NOT to do
- Don't pre-click "Add to stay" before 7 AM — server rejects it (confirmed 2026-04-25).
- Don't add multiple retry strategies that navigate to different URLs. One clean flow, retries via Search button clicks only.
- Don't add `networkidle` waits in the fast path.
- Don't use `page.goto()` at 7 AM — the page is already loaded from pre-navigate, just click Search.
- Don't match the Reserve button by exact name — it's dynamic. Use regex.
- Don't rely on manual checkout at 7 AM — site is too slow. Use Full Checkout mode.

## API Mode ("Nuclear Fast")

`bc_camping_bot/api_booker.py` — Direct HTTP calls bypassing all browser DOM interaction.

### How it works
1. Browser opens just to warm session + extract cookies
2. At 7 AM, fires `GET /api/cart` to get cart UIDs
3. Builds cart commit payload with client-generated `bookingUid` + `resourceZoneBlockerUid` UUIDs
4. Fires `POST /api/cart/commit?isCompleted=false&isSelfCheckIn=false` — one request = in cart
5. If Full Checkout: switches to browser for Reserve + 6 checkout steps (these are multi-step forms)

### Key API details
- `/api/cart` — returns `cartUid`, `createTransactionUid`, `newTransaction` (with `shiftUid`, `userUid`)
- `/api/cart/commit` — POST with full cart payload including `bookings[]` and `resourceZoneBlockers[]`
- `bookingUid` and `resourceZoneBlockerUid` are client-generated UUIDs (uuid4)
- `resourceId` for Taylor Meadows is `-2147481158` (all Garibaldi campsites mapped in `CAMPSITE_RESOURCE_IDS`)
- `bookingCategoryId=4`, `bookingModel=5` for backcountry reservations
- `peopleCapacityCategoryId=-32764`, sub-categories: adult=-32761, youth=-32760, child=-32759
- `equipmentCapacityCategoryId=-32766` (tent pads)

### Fallback
If the API call fails, the bot automatically falls back to browser mode (navigates to results URL, uses `add_to_cart()` from booker.py which handles Search-click retries + proper wait-for-option logic).

### Debugging: capture_real_commit_payload()
`api_booker.py` has a `capture_real_commit_payload(page)` function that intercepts the real fetch request the frontend sends when clicking "Add Area to stay". Use this to compare the real payload vs our constructed one if the API returns 400.

### Lessons from API mode debugging (2026-04-25)
- **Raw httpx gets 403** — must use `page.evaluate()` with JS `fetch()` to inherit browser session cookies/headers
- **API calls from homepage get 400** — must navigate to results page and click Search first to initialize cart context
- **Payload must spread the full cart response** (`...cart`, `...newTxn`) — cherry-picking fields misses server-validated fields. Override only what changes.
- **`isAdult` should be `null`** in bookingCapacityCategoryCounts, not `true`/`false`
- **`completedDate` should be `null`** for new bookings, not `newTxn.createDate`
- **Browser fallback must use `add_to_cart()`** from booker.py — manually waiting for "Add Area to stay" before selecting area is wrong order (button only appears after area selected)

## Dependencies
- playwright (browser automation)
- pywebview (desktop GUI)
- pyyaml (config)
- ntplib (time sync)
- rich (CLI formatting)
- httpx (HTTP/2 client for API mode)

## Park IDs (in booker.py)
Currently only Garibaldi is configured. To add parks, add entries to `PARK_IDS` dict with `transactionLocationId`, `resourceLocationId`, and `mapId` from the BC Parks site.
