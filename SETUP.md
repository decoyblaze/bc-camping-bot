# BC Camping Bot — Setup Guide

This guide walks you through installing and using the bot from scratch. No coding experience needed.

---

## What you need

- A **Mac** (macOS 12 or newer)
- **Google Chrome** installed
- An internet connection
- A **BC Parks account** (for camping bookings — not needed for day-use passes)
  - Create one at [camping.bcparks.ca](https://camping.bcparks.ca) if you don't have one

---

## Step 1: Download the bot

1. Go to **[github.com/decoyblaze/bc-camping-bot](https://github.com/decoyblaze/bc-camping-bot)**
2. Click the green **Code** button, then click **Download ZIP**
3. Open your **Downloads** folder and double-click the ZIP file to unzip it
4. Drag the `bc-camping-bot-main` folder to your **Desktop** (or wherever you want to keep it)
5. Rename it to `bc-camping-bot` (optional, just cleaner)

---

## Step 2: Run the setup script

You only need to do this once. It installs everything the bot needs.

1. Open the **Terminal** app
   - Press `Cmd + Space`, type **Terminal**, and hit Enter
2. Type this command and press Enter:
   ```
   cd ~/Desktop/bc-camping-bot
   ```
   (Change the path if you put the folder somewhere else)
3. Type this command and press Enter:
   ```
   ./setup.sh
   ```
4. Wait for it to finish. You'll see **"Setup Complete"** when it's done.

> **If you get "permission denied":** Run `chmod +x setup.sh launch.command` first, then try `./setup.sh` again.

> **If you get "python3 not found":** Go to [python.org/downloads](https://www.python.org/downloads/) and install the latest Python for Mac. Then run `./setup.sh` again.

---

## Step 3: Launch the bot

**Option A — Double-click** (easiest):
- Open the `bc-camping-bot` folder and double-click **launch.command**
- If macOS blocks it: right-click it, click **Open**, then click **Open** again in the popup

**Option B — From Terminal:**
```
cd ~/Desktop/bc-camping-bot
.venv/bin/camping-bot
```

A small window will open — this is the bot.

---

## How to book: Frontcountry (campsite reservations)

This is for reserving a numbered campsite at parks like Alice Lake, Golden Ears, Cultus Lake, etc.

### Fill in the form

1. **Booking type**: Select **Frontcountry / Campsite**
2. **Park**: Pick your park from the dropdown
3. **Area**: Pick the camping area (e.g. "A (Sites 1-55)" at Alice Lake)
4. **Primary Site**: Enter the campsite number you want most (e.g. `A41` or just `41`)
   - You can add up to 4 backup sites in the fields below — the bot tries them in order
5. **Equipment**: Select what you're bringing (1 Tent, 2 Tents, Van/Camper, etc.)
6. **Arrival date**: The date you want to arrive
7. **Nights**: How many nights you're staying
8. **Booking date**: Auto-calculated — this is when the booking window opens (91 days before arrival)

### Login

1. **Login method**: Pick **"Save separate login session"** (recommended)
2. Click **"Log In to BC Parks"**
3. A browser will open — log in to your BC Parks account
4. Once logged in, come back to the bot and click **"Done — I'm Logged In"**
5. Your login is saved and reused for future runs

### Run it

1. Check **"Full Checkout"** — the bot will complete the entire booking, not just add to cart
2. For practice: check **"Test Timer"** — fires 1 minute from now instead of waiting for 7 AM
3. Click **"Start Bot"**

On the real booking day, uncheck Test Timer and click Start Bot before 7:00 AM. The bot will:
- Pre-load the page and cache everything
- Wait for exactly 7:00:00 AM PT
- Click Search, find your site, and reserve it in under a second
- Complete all checkout steps automatically

---

## How to book: Backcountry

This is for backcountry campsites like Taylor Meadows, Elfin Lakes, and Garibaldi Lake.

### Fill in the form

1. **Booking type**: Select **Backcountry**
2. **Park**: Garibaldi (currently the only backcountry park configured)
3. **Campsite**: Type the campsite name exactly as BC Parks shows it (e.g. `Taylor Meadows`)
4. **Arrival date**: When you want to arrive
5. **Nights**: How many nights
6. **Party size / Tent pads**: Fill in accordingly

### Login and run

Same as frontcountry — log in, check Full Checkout, click Start Bot.

---

## How to book: Day-Use Pass

This is for day-use parking passes and trail passes at parks like Joffre Lakes, Golden Ears, Garibaldi, and Mount Seymour. No BC Parks login needed.

### Fill in the form

1. **Booking type**: Select **Day-Use Pass**
2. **Park**: Pick your park
3. **Facility**: Pick the specific trailhead or parking area
4. **Visit date**: The day you want to visit (passes open 2 days before)
5. **Time slot**: ALL DAY, AM (7am–1pm), or PM (after 1pm) — depends on the facility
6. **Number of passes**: 1–4 for trail passes (parking passes are always 1 per vehicle)
7. **First name, Last name, Email**: Your contact info for the pass

### Run it

1. For practice: check **"Test Timer"**
2. Click **"Start Bot"**
3. The bot opens a browser, fills the form at 7 AM, and handles everything
4. **When you see "Click the CAPTCHA checkbox"** — go to the browser and click the checkbox. The bot handles everything else after that.

Your pass confirmation and registration number will appear in the bot log.

---

## Supported parks

### Frontcountry (campsites)
Alice Lake, Birkenhead Lake, Chilliwack Lake, Cultus Lake, Golden Ears, Inland Lake, Nairn Falls, Porpoise Bay, Porteau Cove, Rolley Lake, Saltery Bay, Sasquatch, Silver Lake

### Backcountry
Garibaldi (Taylor Meadows, Elfin Lakes, Garibaldi Lake, etc.)

### Day-Use Passes
Golden Ears (4 parking areas), Joffre Lakes (trail pass), Garibaldi (3 trailheads), Mount Seymour (parking)

---

## Tips

- **Always do a test run first.** Check "Test Timer" and run through the full flow to make sure everything works. The test fires 1 minute from now instead of 7 AM.
- **Use Full Checkout mode.** At 7 AM the BC Parks site is extremely slow. The bot clicks through checkout far faster than you can manually.
- **Start the bot 5–10 minutes before 7 AM** on the real day. It pre-loads everything and waits.
- **Don't close the browser window** that the bot opens. Your cart is tied to that browser session.
- **Frontcountry sites**: enter backup sites in priority order. If your first choice is taken, the bot automatically tries the next one.
- **Day-use CAPTCHA**: the bot handles everything except the initial CAPTCHA checkbox — you need to click that yourself when prompted.

---

## Troubleshooting

**"Permission denied" when running setup.sh or launch.command**
Open Terminal and run:
```
chmod +x ~/Desktop/bc-camping-bot/setup.sh ~/Desktop/bc-camping-bot/launch.command
```

**"Python 3 not found"**
Download and install Python from [python.org/downloads](https://www.python.org/downloads/). Pick the latest version for macOS.

**The bot window doesn't open**
Try launching from Terminal instead:
```
cd ~/Desktop/bc-camping-bot
.venv/bin/camping-bot
```
This will show any error messages.

**"Login session expired" or booking fails with auth error**
Click "Log In to BC Parks" again to refresh your saved login session.

**Site "not found on map"**
Make sure you selected the right **Area** for your site. For example, site 41 at Alice Lake is in area "A (Sites 1-55)". You can enter `A41` or just `41`.

**Bot says "all cycles exhausted"**
The site(s) you wanted were already taken. At 7 AM, popular sites sell out in seconds. Add more backup sites to improve your chances.

**Chrome won't close / reopens weirdly**
The bot uses its own separate browser — it doesn't touch your Chrome. If something goes wrong, just close any extra browser windows manually.
