# BC Camping Bot

Automated booking bot for BC Parks backcountry campsites. Fires at exactly 7:00 AM PT when the booking window opens.

## Setup (one-time)

```bash
cd bc-camping-bot
./setup.sh
```

Requires Python 3.9+ and macOS. The setup script creates a virtual environment, installs dependencies, and downloads the browser.

## Launch

Double-click `launch.command`, or:

```bash
.venv/bin/camping-bot
```

## How to use

1. **Fill in booking details** — park, campsite, arrival date, party size, tent pads
2. **Set the booking date** — auto-calculated as 91 days before arrival (when BC Parks opens the window)
3. **Choose login method** — "Use my Chrome profile" is easiest (close Chrome first)
4. **Select mode** — "Full Checkout" is recommended (bot completes all 6 checkout steps automatically)
5. **Check "Test Timer"** for practice runs (fires 1 min from now instead of 7 AM)
6. **Click "Start Bot"** — it pre-loads the page, waits for 7 AM, then books as fast as possible

## Tips

- **Close Chrome before launching** if using Chrome profile login
- **Use Full Checkout mode** — the site is too slow at 7 AM to checkout manually
- **Test Timer** lets you do end-to-end dry runs any time of day
- The bot pre-loads everything before 7 AM so it only needs to click Search + Add at go time
- Typical speed: 0.1–0.3s to cart, ~10s total including checkout

## Currently supported parks

- Garibaldi (all backcountry campsites: Taylor Meadows, Elfin Lakes, Garibaldi Lake, etc.)

More parks can be added to `PARK_IDS` in `booker.py`.
