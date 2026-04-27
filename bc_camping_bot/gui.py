"""Desktop GUI for BC Camping Bot — uses pywebview for reliable macOS rendering."""

import asyncio
import json
import os
import queue
import re
import subprocess
import sys
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

import webview

from .config import Booking
from .stealth import apply_stealth, get_stealth_config

if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).parent.parent.parent
else:
    PROJECT_ROOT = Path(__file__).parent.parent

DATA_DIR = Path.home() / ".bc-camping-bot"


def get_data_dir():
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "sessions").mkdir(exist_ok=True)
    return DATA_DIR


HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>BC Camping Bot</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f5f5f7;
    color: #1d1d1f;
    padding: 20px;
  }
  h1 { font-size: 22px; text-align: center; margin-bottom: 16px; }
  .card {
    background: #fff;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }
  .card h2 {
    font-size: 14px;
    color: #86868b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 14px;
  }
  .field {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
  }
  .field label {
    width: 130px;
    font-size: 14px;
    font-weight: 500;
    flex-shrink: 0;
  }
  .field input, .field select {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid #d2d2d7;
    border-radius: 8px;
    font-size: 14px;
    background: #fafafa;
    outline: none;
  }
  .field input:focus, .field select:focus {
    border-color: #0071e3;
    box-shadow: 0 0 0 3px rgba(0,113,227,0.15);
  }
  .field .hint {
    font-size: 12px;
    color: #86868b;
    margin-left: 8px;
    white-space: nowrap;
  }
  .buttons {
    display: flex;
    gap: 8px;
    margin-bottom: 14px;
    flex-wrap: wrap;
  }
  .btn {
    padding: 10px 16px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }
  .btn:active { transform: scale(0.97); }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-primary { background: #0071e3; color: #fff; flex: 2; }
  .btn-primary:hover:not(:disabled) { background: #0077ED; }
  .btn-secondary { background: #e8e8ed; color: #1d1d1f; flex: 1; }
  .btn-secondary:hover:not(:disabled) { background: #d2d2d7; }
  .btn-danger { background: #ff3b30; color: #fff; flex: 1; }
  .btn-danger:hover:not(:disabled) { background: #e0342b; }
  #log {
    background: #1e1e1e;
    color: #d4d4d4;
    font-family: "SF Mono", Menlo, Monaco, monospace;
    font-size: 12px;
    border-radius: 8px;
    padding: 12px;
    height: 200px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
    user-select: text;
    -webkit-user-select: text;
    cursor: text;
  }
  #log .time { color: #6a9955; }
  #log .error { color: #f44747; }
  #log .success { color: #4ec9b0; }
  #status {
    text-align: center;
    padding: 8px;
    font-size: 13px;
    font-weight: 500;
    border-radius: 8px;
    margin-top: 10px;
  }
  .status-ready { background: #e8e8ed; color: #86868b; }
  .status-running { background: #e3f2fd; color: #0071e3; }
  .status-waiting { background: #fff3e0; color: #ff9500; }
  .status-success { background: #e8f5e9; color: #34c759; }
  .status-error { background: #fce4ec; color: #ff3b30; }
</style>
</head>
<body>
  <h1>BC Camping Bot</h1>

  <div class="card">
    <h2>Booking Details</h2>
    <div class="field">
      <label>Park</label>
      <select id="park">
        <option selected>Garibaldi</option>
        <option>Berg Lake Trail</option>
        <option>Cathedral</option>
        <option>E. C. Manning</option>
        <option>Joffre Lakes</option>
        <option>Mount Assiniboine</option>
      </select>
    </div>
    <div class="field">
      <label>Campsite / Area</label>
      <input id="campsite" value="Taylor Meadows" placeholder="e.g. Taylor Meadows or 'any'">
    </div>
    <div class="field">
      <label>Arrival Date</label>
      <input id="arrival" type="date" value="2026-07-25">
    </div>
    <div class="field">
      <label>Departure Date</label>
      <input id="departure" type="date" value="2026-07-26">
    </div>
    <div class="field">
      <label>Nights</label>
      <input id="nights" type="number" value="1" min="1" max="14" style="width:80px;flex:none">
    </div>
    <div class="field">
      <label>Party Size</label>
      <input id="people" type="number" value="6" min="1" max="20" style="width:80px;flex:none">
    </div>
    <div class="field">
      <label>Tent Pads</label>
      <input id="pads" type="number" value="3" min="1" max="10" style="width:80px;flex:none">
    </div>
    <div class="field">
      <label>Equipment</label>
      <select id="equipment">
        <option selected>tent</option>
        <option>tarp</option>
        <option>hammock</option>
      </select>
    </div>
    <div class="field">
      <label>Booking Opens</label>
      <input id="booking_date" type="date" value="2026-04-25">
      <span class="hint" id="booking_hint">7:00 AM PT on Apr 25</span>
    </div>
    <div class="field">
      <label>Login Method</label>
      <select id="login_method" onchange="toggleLoginFields()">
        <option value="chrome" selected>Use my Chrome profile (easiest)</option>
        <option value="session">Save separate login session</option>
      </select>
    </div>
    <div class="field" id="chrome_profile_row">
      <label>Chrome Profile</label>
      <select id="chrome_profile">CHROME_PROFILE_OPTIONS</select>
    </div>
    <div class="field" id="session_name_row" style="display:none">
      <label>Session Name</label>
      <input id="session_name" value="SESSION_NAME_PLACEHOLDER" placeholder="Used for login session">
    </div>
    <div class="field">
      <label>Mode</label>
      <select id="mode">
        <option value="cart" selected>Add to Cart (you checkout manually)</option>
        <option value="full">Full Checkout (bot completes purchase)</option>
      </select>
    </div>
    <div class="field">
      <label>Test Timer</label>
      <input type="checkbox" id="test_timer" style="width:auto;flex:none">
      <span class="hint">Fires 1 min from now instead of 7 AM</span>
    </div>
  </div>

  <div class="buttons">
    <button class="btn btn-secondary" id="btn_login" onclick="callApi('save_session')">
      1. Save Login
    </button>
    <button class="btn btn-primary" id="btn_start" onclick="callApi('start_bot')">
      2. Start Bot
    </button>
    <button class="btn btn-secondary" id="btn_test" onclick="callApi('test_run')">
      Test Run
    </button>
    <button class="btn btn-danger" id="btn_stop" onclick="callApi('stop')" disabled>
      Stop
    </button>
    <button class="btn btn-success" id="btn_confirm_login" onclick="callApi('confirm_login')" style="display:none">
      Done — I'm Logged In
    </button>
  </div>

  <div class="card">
    <h2 style="display:flex;justify-content:space-between;align-items:center">
      Log
      <button id="log-copy-btn" onclick="copyLog()" style="font-size:11px;padding:4px 10px;border:1px solid #d2d2d7;border-radius:6px;background:#fafafa;cursor:pointer;text-transform:none;letter-spacing:0">Copy Log</button>
    </h2>
    <div id="log"></div>
  </div>

  <div id="status" class="status-ready">Ready</div>

  <script>
    const arrivalEl = document.getElementById('arrival');
    const departureEl = document.getElementById('departure');
    const nightsEl = document.getElementById('nights');
    const bookingEl = document.getElementById('booking_date');
    const hintEl = document.getElementById('booking_hint');

    function updateDeparture() {
      const arrival = new Date(arrivalEl.value + 'T00:00:00');
      const nights = parseInt(nightsEl.value) || 1;
      const dep = new Date(arrival);
      dep.setDate(dep.getDate() + nights);
      departureEl.value = dep.toISOString().split('T')[0];
    }

    function updateBookingDate() {
      const arrival = new Date(arrivalEl.value + 'T00:00:00');
      const bdate = new Date(arrival);
      bdate.setDate(bdate.getDate() - 91);
      bookingEl.value = bdate.toISOString().split('T')[0];
      const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      hintEl.textContent = '7:00 AM PT on ' + months[bdate.getMonth()] + ' ' + bdate.getDate();
    }

    arrivalEl.addEventListener('change', () => { updateDeparture(); updateBookingDate(); });
    nightsEl.addEventListener('change', updateDeparture);

    function toggleLoginFields() {
      const method = document.getElementById('login_method').value;
      document.getElementById('chrome_profile_row').style.display = method === 'chrome' ? 'flex' : 'none';
      document.getElementById('session_name_row').style.display = method === 'session' ? 'flex' : 'none';
      document.getElementById('btn_login').style.display = method === 'session' ? '' : 'none';
    }
    toggleLoginFields();

    function getFormData() {
      return {
        park: document.getElementById('park').value,
        campsite: document.getElementById('campsite').value,
        arrival: arrivalEl.value,
        departure: departureEl.value,
        nights: parseInt(nightsEl.value),
        people: parseInt(document.getElementById('people').value),
        pads: parseInt(document.getElementById('pads').value),
        equipment: document.getElementById('equipment').value,
        booking_date: bookingEl.value,
        session_name: document.getElementById('session_name').value,
        mode: document.getElementById('mode').value,
        login_method: document.getElementById('login_method').value,
        chrome_profile: document.getElementById('chrome_profile').value,
        test_timer: document.getElementById('test_timer').checked,
      };
    }

    window.getFormData = getFormData;

    function appendLog(msg, cls) {
      const log = document.getElementById('log');
      const now = new Date().toLocaleTimeString();
      const line = document.createElement('div');
      line.innerHTML = '<span class="time">[' + now + ']</span> ' +
        (cls ? '<span class="' + cls + '">' + msg + '</span>' : msg);
      log.appendChild(line);
      log.scrollTop = log.scrollHeight;
    }

    function setStatus(text, level) {
      const el = document.getElementById('status');
      el.textContent = text;
      el.className = 'status-' + (level || 'ready');
    }

    function setRunning(running) {
      document.getElementById('btn_login').disabled = running;
      document.getElementById('btn_start').disabled = running;
      document.getElementById('btn_test').disabled = running;
      document.getElementById('btn_stop').disabled = !running;
    }

    window.appendLog = appendLog;
    window.setStatus = setStatus;
    window.setRunning = setRunning;

    function copyLog() {
      const log = document.getElementById('log');
      const text = log.innerText;
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      const btn = document.querySelector('#log-copy-btn');
      if (btn) { btn.textContent = 'Copied!'; setTimeout(() => btn.textContent = 'Copy Log', 1500); }
    }

    function callApi(method) {
      if (window.pywebview && window.pywebview.api && window.pywebview.api[method]) {
        window.pywebview.api[method]();
      } else {
        appendLog('API not ready yet — try again in a moment', 'error');
      }
    }

    async function pollLogs() {
      if (!window.pywebview || !window.pywebview.api) {
        setTimeout(pollLogs, 300);
        return;
      }
      try {
        const msgs = await window.pywebview.api.get_logs();
        if (msgs) {
          for (const m of msgs) {
            if (m[0] === 'log') appendLog(m[1]);
            else if (m[0] === 'error') appendLog(m[1], 'error');
            else if (m[0] === 'success') appendLog(m[1], 'success');
            else if (m[0] === 'status') setStatus(m[1], m[2]);
            else if (m[0] === 'running') setRunning(m[1]);
            else if (m[0] === 'show_confirm') {
              document.getElementById('btn_confirm_login').style.display = m[1] ? '' : 'none';
            }
          }
        }
      } catch(e) {}
      setTimeout(pollLogs, 200);
    }
    pollLogs();
  </script>
</body>
</html>
"""


class Api:
    def __init__(self):
        self._data_dir = get_data_dir()
        self._log_queue = queue.Queue()
        self._worker_thread = None
        self._worker_loop = None
        self._worker_task = None
        self._login_done = threading.Event()
        self._window = None

    def set_window(self, window):
        self._window = window

    def get_logs(self):
        msgs = []
        while True:
            try:
                msgs.append(self._log_queue.get_nowait())
            except queue.Empty:
                break
        return msgs if msgs else None

    def _log(self, text):
        self._log_queue.put(("log", text))

    def _error(self, text):
        self._log_queue.put(("error", text))

    def _success(self, text):
        self._log_queue.put(("success", text))

    def _status(self, text, level="ready"):
        self._log_queue.put(("status", text, level))

    def _set_running(self, running):
        self._log_queue.put(("running", running))

    def _get_form_data(self):
        return self._window.evaluate_js("getFormData()")

    def _build_booking(self, data):
        session_name = data["session_name"].strip() or "default"
        if not session_name.endswith(".json"):
            session_name += ".json"

        arrival = date.fromisoformat(data["arrival"])
        booking_date = date.fromisoformat(data["booking_date"]) if data.get("booking_date") else None

        return Booking(
            name=f"{data['park']} — {data['campsite']}",
            park=data["park"],
            campsite=data["campsite"].strip() or "any",
            arrival_date=arrival,
            num_nights=data["nights"],
            num_people=data["people"],
            num_tent_pads=data["pads"],
            equipment_type=data["equipment"],
            session_file=str(self._data_dir / "sessions" / session_name),
            booking_date=booking_date,
        )

    # ── Save Session ──────────────────────────────────────────

    def save_session(self):
        data = self._get_form_data()
        self._set_running(True)
        self._status("Opening browser for login...", "running")
        self._log("Opening browser — log in to camping.bcparks.ca")

        def run():
            try:
                asyncio.run(self._save_session_async(data))
            except Exception as e:
                self._error(f"Error: {e}")
                self._status("Failed", "error")
            finally:
                self._set_running(False)

        self._worker_thread = threading.Thread(target=run, daemon=True)
        self._worker_thread.start()

    async def _save_session_async(self, data):
        session_name = data["session_name"].strip() or "default"
        if not session_name.endswith(".json"):
            session_name += ".json"
        output_path = self._data_dir / "sessions" / session_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        config = get_stealth_config()

        from playwright.async_api import async_playwright

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

            self._log("Navigating to camping.bcparks.ca...")
            await page.goto("https://camping.bcparks.ca")
            self._log("Browser open. Log in now, then come back here.")
            self._status("Waiting for login — check the browser window", "waiting")

            self._login_done.clear()
            self._log_queue.put(("show_confirm", True))
            self._log("After logging in, click the green 'Done — I'm Logged In' button.")

            self._login_done.wait()
            self._log_queue.put(("show_confirm", False))

            cookies = await context.cookies()
            storage = await context.storage_state()
            session_data = {"cookies": cookies, "storage_state": storage}
            output_path.write_text(json.dumps(session_data, indent=2))

            self._success(f"Session saved: {session_name}")
            self._status("Login saved!", "success")
            await browser.close()

    def confirm_login(self):
        self._login_done.set()

    # ── Start Bot / Test Run ──────────────────────────────────

    def start_bot(self):
        try:
            data = self._get_form_data()
            mode = data.get("mode", "cart")
            test_timer = data.get("test_timer", False)
            full_checkout = mode == "full"
            self._run_bot(test_run=False, full_checkout=full_checkout,
                          test_timer=test_timer)
        except Exception as e:
            import traceback
            self._error(f"start_bot crashed: {e}")
            self._error(traceback.format_exc())

    def test_run(self):
        self._run_bot(test_run=True, full_checkout=False)

    def _run_bot(self, test_run, full_checkout, test_timer=False):
        data = self._get_form_data()
        try:
            booking = self._build_booking(data)
        except Exception as e:
            self._error(f"Invalid input: {e}")
            return

        use_chrome = data.get("login_method", "chrome") == "chrome"
        chrome_profile = data.get("chrome_profile", "Default")

        if not use_chrome:
            session_path = Path(booking.session_file)
            if not session_path.exists():
                self._error("No saved login found. Click '1. Save Login' first.")
                return

        self._set_running(True)
        if test_run:
            label = "Test Run"
        elif full_checkout:
            label = "Full Checkout"
        else:
            label = "Add to Cart"
        self._status(f"{label} in progress...", "running")
        self._log(f"--- {label} ---")
        self._log(f"  Park: {booking.park}")
        self._log(f"  Campsite: {booking.campsite}")
        self._log(f"  Arrival: {booking.arrival_date}")
        if not test_run:
            if test_timer:
                self._log(f"  TEST TIMER: firing 1 min from now")
            else:
                self._log(f"  Opens: {booking.booking_opens_at.strftime('%Y-%m-%d %H:%M:%S')} PT")
            self._log(f"  Mode: {label}")

        def run():
            loop = asyncio.new_event_loop()
            self._worker_loop = loop
            try:
                loop.run_until_complete(
                    self._run_booking(booking, test_run=test_run, full_checkout=full_checkout,
                                      use_chrome=use_chrome, test_timer=test_timer,
                                      chrome_profile=chrome_profile)
                )
            except asyncio.CancelledError:
                self._log("Cancelled.")
                self._status("Cancelled", "error")
            except Exception as e:
                import traceback
                self._error(f"Error: {e}")
                self._error(traceback.format_exc())
                self._status("Failed", "error")
            finally:
                self._set_running(False)
                loop.close()

        self._worker_thread = threading.Thread(target=run, daemon=True)
        self._worker_thread.start()

    async def _run_booking(self, booking, test_run, full_checkout, use_chrome=False, test_timer=False, chrome_profile="Default"):
        self._worker_task = asyncio.current_task()
        from datetime import timedelta as td

        from playwright.async_api import async_playwright

        from .booker import (
            build_results_url,
            launch_with_chrome_profile,
            load_session,
            pre_navigate,
            reopen_chrome,
        )
        from .notify import notify
        from .timesync import get_ntp_offset, precise_time, wait_until

        ntp_offset = get_ntp_offset()

        async with async_playwright() as pw:
            browser = None
            if use_chrome:
                self._log(f"Launching with Chrome profile '{chrome_profile}'...")
                try:
                    context, page = await launch_with_chrome_profile(pw, profile=chrome_profile, log=self._log)
                except Exception as e:
                    self._error(f"Failed to launch Chrome profile: {e}")
                    return
                await apply_stealth(page)
                self._success("Chrome profile loaded — logged in.")
            else:
                browser = await pw.chromium.launch(headless=False)
                context = await load_session(browser.new_context, booking)
                page = await context.new_page()
                await apply_stealth(page)

            added_to_cart = False
            try:
                # ── Test Run: skip timing, run the full bot flow immediately ──
                if test_run:
                    import time as _time
                    import sys as _sys

                    print("[TEST RUN] Starting...", file=_sys.stderr, flush=True)
                    self._log("Going straight to results page...")
                    t0 = _time.monotonic()
                    results_url = build_results_url(booking)
                    await page.goto(results_url, wait_until="domcontentloaded")
                    self._success(f"Results page loaded. ({_time.monotonic()-t0:.1f}s)")
                    print("[TEST RUN] Results page loaded", file=_sys.stderr, flush=True)

                    # Capture ALL requests via Playwright's native event listener
                    self._log("Setting up request capture...")
                    captured_payloads = []
                    def on_request(request):
                        if request.method == "POST":
                            captured_payloads.append({
                                "url": request.url,
                                "method": request.method,
                                "body": request.post_data,
                            })
                            print(f"[CAPTURED] POST {request.url}", file=_sys.stderr, flush=True)
                            self._log(f"CAPTURED: POST {request.url.split('?')[0]}")
                    page.on("request", on_request)

                    self._log("Selecting area + Add to stay + Reserve...")
                    t1 = _time.monotonic()
                    try:
                        from .booker import select_area_and_reserve
                        await select_area_and_reserve(page, booking.campsite, self._log)
                        self._success(f"IN CART! ({_time.monotonic()-t1:.1f}s)")
                        print("[TEST RUN] IN CART!", file=_sys.stderr, flush=True)
                    except Exception as e:
                        self._error(f"Reserve FAILED ({_time.monotonic()-t1:.1f}s): {e}")
                        self._log("(Expected if booking window isn't open yet)")
                        print(f"[TEST RUN] FAILED: {e}", file=_sys.stderr, flush=True)

                    page.remove_listener("request", on_request)

                    dump_path = self._data_dir / "captured_payload.json"
                    dump_path.write_text(json.dumps(captured_payloads, indent=2))
                    self._log(f"Captured {len(captured_payloads)} POST request(s) → {dump_path}")
                    print(f"[TEST RUN] Saved {len(captured_payloads)} requests to {dump_path}", file=_sys.stderr, flush=True)

                    total = _time.monotonic() - t0
                    self._log(f"=== TOTAL: {total:.1f}s ===")
                    self._success("Test complete. Browser stays open for 15s.")
                    self._status("Test complete", "success")
                    await asyncio.sleep(15)
                    return

                # ── Real Run: timing + pre-load + attempts ──
                if test_timer:
                    target = precise_time(ntp_offset) + td(seconds=60)
                    self._log(f"TEST TIMER: target set to {target.strftime('%H:%M:%S')}")
                else:
                    target = booking.booking_opens_at
                remaining = (target - precise_time(ntp_offset)).total_seconds()

                if remaining > 120:
                    self._log("Warming session...")
                    await page.goto("https://camping.bcparks.ca", wait_until="domcontentloaded")
                    self._success("Session warm.")
                    pre_target = target - td(seconds=60)
                    wait_pre = (pre_target - precise_time(ntp_offset)).total_seconds()
                    self._log(f"Waiting {wait_pre:.0f}s before pre-loading results...")
                    self._status("Waiting to pre-load...", "waiting")
                    wait_until(pre_target, ntp_offset)

                self._log("Pre-loading results page (caching assets)...")
                await pre_navigate(page, booking)
                self._success("Results page cached.")

                from .booker import add_to_cart, dismiss_cookie_consent, click_search_button, pre_select_area

                self._log("Pre-selecting area (rendering Build your stay)...")
                await pre_select_area(page, booking.campsite, self._log)
                self._success("Area pre-selected. Standing by.")

                remaining = (target - precise_time(ntp_offset)).total_seconds()
                if remaining > 0:
                    self._log(f"Waiting {remaining:.0f}s for 7:00 AM...")
                    self._status(f"Waiting for 7:00 AM PT ({remaining:.0f}s)...", "waiting")
                    wait_until(target, ntp_offset)

                import time as _time

                self._success("GO! Booking window open.")
                self._status("Booking NOW...", "running")
                t_start = _time.monotonic()

                # ══════════════════════════════════════════════════════
                # ADD TO STAY — the bot's entire reason for existing.
                # Uses add_to_cart() which handles Search → select area → Add.
                # Retries the full cycle aggressively — up to 10 attempts.
                # ══════════════════════════════════════════════════════
                from .booker import add_to_cart
                added_to_cart = False
                reserve_btn = None

                for cycle in range(10):
                    try:
                        if cycle > 0:
                            self._log(f"--- Retry cycle {cycle+1}/10 ---")
                        await add_to_cart(page, booking.campsite, self._log)
                        t_added = _time.monotonic()
                        self._log(f"Add to stay clicked ({t_added - t_start:.2f}s)")

                        reserve_btn = page.get_by_role("button", name=re.compile(r"^Reserve Area:"))
                        await reserve_btn.wait_for(state="visible", timeout=30000)
                        t_confirmed = _time.monotonic()
                        added_to_cart = True
                        self._success(f"IN CART! ({t_confirmed - t_start:.2f}s)")
                        notify("Camping Bot", f"IN CART in {t_confirmed - t_start:.2f}s! {booking.park}")
                        break
                    except Exception as e:
                        self._error(f"Attempt {cycle+1} failed: {e}")
                        if cycle < 9:
                            self._log("Retrying...")
                        else:
                            self._error("All 10 attempts exhausted.")
                            self._log(">>> Check the browser — you may need to add to cart manually. <<<")
                            notify("Camping Bot", f"FAILED to add to cart after 10 attempts: {booking.park}")

                # ══════════════════════════════════════════════════════
                # EVERYTHING BELOW IS BEST EFFORT.
                # The booking is in the cart — that's the hard part done.
                # If anything fails here, the browser stays open and
                # the user finishes manually. No exceptions, no crashes.
                # ══════════════════════════════════════════════════════
                if added_to_cart and reserve_btn:
                    try:
                        await reserve_btn.click()
                        t_reserved = _time.monotonic()
                        self._success(f"Reserved! ({t_reserved - t_start:.2f}s)")

                        try:
                            dialog = page.get_by_role("dialog", name="Park Alerts")
                            if await dialog.is_visible(timeout=300):
                                await dialog.get_by_role("button", name="Acknowledge").click()
                        except Exception:
                            pass

                        t_cart = _time.monotonic() - t_start

                        if full_checkout:
                            self._log("--- Starting checkout ---")
                            from .booker import complete_checkout
                            await complete_checkout(page, self._log)
                            t_total = _time.monotonic() - t_start
                            self._log(f"=== TOTAL: {t_total:.2f}s (cart: {t_cart:.2f}s + checkout: {t_total - t_cart:.2f}s) ===")
                            self._success("BOOKING COMPLETE!")
                            self._status(f"BOOKED! (cart: {t_cart:.1f}s, total: {t_total:.1f}s)", "success")
                            notify("Camping Bot", f"Booked {booking.park}! Cart: {t_cart:.1f}s, Total: {t_total:.1f}s")
                        else:
                            self._success("IN CART! You have ~15 min to checkout.")
                            self._status(f"IN CART ({t_cart:.1f}s) — checkout in browser!", "success")
                            notify("Camping Bot", f"{booking.park} in cart in {t_cart:.1f}s! Checkout now!")
                    except Exception as e:
                        self._error(f"Auto-checkout failed: {e}")
                        self._log(">>> IT'S IN YOUR CART — finish checkout manually in the browser! <<<")
                        self._status("IN CART — finish checkout manually!", "waiting")
                        notify("Camping Bot", f"IN CART but auto-checkout failed — finish manually!")

                # Browser ALWAYS stays open — never close it after booking flow starts
                self._log("Browser will stay open. Close it manually when done.")
                while True:
                    await asyncio.sleep(60)
            except asyncio.CancelledError:
                self._log("Cancelled.")
                self._status("Cancelled", "error")
            except Exception as e:
                self._error(f"Unexpected error: {e}")
                self._log("Browser will stay open. Close it manually when done.")
                self._status("Error — check browser", "error")
                while True:
                    await asyncio.sleep(60)

    # ── Stop ──────────────────────────────────────────────────

    def stop(self):
        if self._worker_loop and self._worker_task:
            self._worker_loop.call_soon_threadsafe(self._worker_task.cancel)
        self._login_done.set()
        self._log("Stopping...")
        self._status("Stopping...", "waiting")


def main():
    default_name = os.environ.get("USER", "default")

    chrome_data = Path.home() / "Library/Application Support/Google/Chrome"
    profile_options = ""
    for d in sorted(chrome_data.iterdir()):
        if not d.is_dir():
            continue
        prefs = d / "Preferences"
        if not prefs.exists():
            continue
        name = d.name
        if name == "System Profile":
            continue
        try:
            import json as _json
            p = _json.loads(prefs.read_text())
            accts = p.get("account_info", [])
            label = name
            if accts:
                label += f" ({accts[0].get('email', '')})"
            selected = " selected" if accts else ""
            profile_options += f'<option value="{name}"{selected}>{label}</option>\n'
        except Exception:
            profile_options += f'<option value="{name}">{name}</option>\n'
    if not profile_options:
        profile_options = '<option value="Default">Default</option>'

    html = HTML.replace("SESSION_NAME_PLACEHOLDER", default_name)
    html = html.replace("CHROME_PROFILE_OPTIONS", profile_options)

    api = Api()

    def check_browsers():
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                _ = p.chromium.executable_path
        except Exception:
            api._log("First run — installing browser (one-time)...")
            api._status("Installing browser...", "waiting")
            try:
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    check=True, capture_output=True, timeout=300,
                )
                api._success("Browser installed.")
                api._status("Ready", "ready")
            except Exception as e:
                api._error(f"Failed to install browser: {e}")

    threading.Thread(target=check_browsers, daemon=True).start()

    window = webview.create_window(
        "BC Camping Bot",
        html=html,
        js_api=api,
        width=660,
        height=860,
        resizable=True,
        min_size=(500, 600),
    )
    api.set_window(window)
    webview.start()


if __name__ == "__main__":
    main()
