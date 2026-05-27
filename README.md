# BC Camping Bot

Automated booking bot for BC Parks. Fires at exactly 7:00 AM PT when the booking window opens and reserves your campsite or day-use pass before they sell out.

Supports three booking types:
- **Frontcountry campsites** — numbered sites at 13 parks (Alice Lake, Golden Ears, Cultus Lake, etc.)
- **Backcountry campsites** — Garibaldi Park (Taylor Meadows, Elfin Lakes, Garibaldi Lake, etc.)
- **Day-use passes** — parking and trail passes at Joffre Lakes, Golden Ears, Garibaldi, Mount Seymour

## How it works

1. You fill in what you want to book (park, site, dates)
2. The bot pre-loads the BC Parks website and caches everything
3. At exactly 7:00:00 AM PT, it clicks Search and reserves your site in under a second
4. In Full Checkout mode, it completes all 6 checkout steps automatically

Typical speed: **0.1–0.3s** to add a site to cart. The bot is faster than any human can click.

## Quick start

Requires macOS and Google Chrome.

```bash
cd bc-camping-bot
./setup.sh            # one-time: installs everything
```

Then double-click **launch.command** to open the bot, or run:

```bash
.venv/bin/camping-bot
```

**First time?** See the **[full setup guide (SETUP.md)](SETUP.md)** — walks you through everything step by step, no coding experience needed.

## Supported parks

### Frontcountry (campsites)
Alice Lake, Birkenhead Lake, Chilliwack Lake, Cultus Lake, Golden Ears, Inland Lake, Nairn Falls, Porpoise Bay, Porteau Cove, Rolley Lake, Saltery Bay, Sasquatch, Silver Lake

### Backcountry
Garibaldi (all backcountry campsites)

### Day-Use Passes
Golden Ears (4 parking areas), Joffre Lakes (trail pass), Garibaldi (3 trailheads), Mount Seymour (parking)

## Features

- **NTP-synced timer** — hits 7:00:00.000 AM with millisecond precision
- **Full automated checkout** — all 6 steps from cart to payment page
- **Frontcountry fallback sites** — specify up to 5 sites in priority order; if #1 is taken, it tries #2, etc.
- **Day-use CAPTCHA handling** — bot fills everything, you just click one checkbox
- **Test Timer mode** — practice the full flow any time of day (fires 1 min from now)
- **Saved login sessions** — log in once, reuse across runs
- **Pre-loading** — caches all JS/CSS/API assets before 7 AM so the actual booking is instant

## Tips

- Always do a **test run first** (check "Test Timer")
- Use **Full Checkout** mode — the site is too slow at 7 AM to checkout manually
- Start the bot **5–10 minutes before 7 AM** on the real day
- Don't close the browser window the bot opens — your cart is tied to that session
- For day-use passes, the bot handles everything except the CAPTCHA checkbox

## Troubleshooting

See the [setup guide](SETUP.md#troubleshooting) for common issues and fixes.
