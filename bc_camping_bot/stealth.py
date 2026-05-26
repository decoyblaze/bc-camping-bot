"""Stealth browser configuration to avoid bot detection.

The site uses Queue-IT for virtual waiting rooms during high traffic.
Queue-IT checks: navigator.webdriver, chrome runtime, plugins, languages,
WebGL renderer, and general browser fingerprint consistency.
"""

import random
import sys

MAC_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

WINDOWS_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
]

USER_AGENTS = WINDOWS_USER_AGENTS if sys.platform == "win32" else MAC_USER_AGENTS

STEALTH_JS = """
() => {
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true,
    });

    if (!window.chrome) {
        window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {};
    }
    window.chrome.runtime.connect = function() { return { onMessage: { addListener: function(){} }, postMessage: function(){} }; };
    window.chrome.runtime.sendMessage = function(msg, cb) { if (cb) cb(); };

    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);

    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const arr = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' },
            ];
            arr.item = (i) => arr[i];
            arr.namedItem = (n) => arr.find(p => p.name === n);
            arr.refresh = () => {};
            return arr;
        },
    });

    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-CA', 'en-US', 'en'],
    });

    delete navigator.__proto__.webdriver;

    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8,
    });

    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8,
    });

    // Hide CDP artifacts that Cloudflare Turnstile probes
    var cdc_props = Object.getOwnPropertyNames(window).filter(function(p) {
        return p.match(/cdc_|__playwright|__driver/);
    });
    for (var i = 0; i < cdc_props.length; i++) {
        delete window[cdc_props[i]];
    }

    // Fake connection.rtt (Turnstile checks for 0 = automated)
    if (navigator.connection) {
        Object.defineProperty(navigator.connection, 'rtt', { get: () => 50 });
    }

    var originalAttachShadow = Element.prototype.attachShadow;
    Element.prototype.attachShadow = function() {
        return originalAttachShadow.apply(this, arguments);
    };
}
"""


def get_stealth_config():
    user_agent = random.choice(USER_AGENTS)
    return {
        "user_agent": user_agent,
        "locale": "en-CA",
        "timezone_id": "America/Vancouver",
    }


async def apply_stealth(page):
    await page.add_init_script(STEALTH_JS)


async def human_delay(min_ms=50, max_ms=150):
    """Minimal random delay — fast but not instant."""
    import asyncio
    delay = random.uniform(min_ms / 1000, max_ms / 1000)
    await asyncio.sleep(delay)


async def human_click(page, selector):
    """Click with slight randomization to avoid perfect-center clicks."""
    element = await page.wait_for_selector(selector, timeout=10000)
    box = await element.bounding_box()
    if box:
        x = box["x"] + box["width"] * random.uniform(0.35, 0.65)
        y = box["y"] + box["height"] * random.uniform(0.35, 0.65)
        await page.mouse.click(x, y)
    else:
        await element.click()


async def human_type(page, selector, text):
    """Type text with minimal per-key delay."""
    await human_click(page, selector)
    for char in text:
        await page.keyboard.press(char)
        await human_delay(20, 60)
