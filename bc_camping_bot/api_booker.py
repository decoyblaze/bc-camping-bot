"""API-mode booking — direct API calls instead of clicking through the DOM.

Bypasses all DOM interaction by executing fetch() calls inside the Playwright
page context. This inherits all cookies, CSRF tokens, and headers automatically.

The flow:
1. Browser loads camping.bcparks.ca (for valid session)
2. At 7 AM: page.evaluate() runs fetch('/api/cart') + fetch('/api/cart/commit')
3. Two fetch calls = in cart (~50ms vs ~100-300ms for DOM clicks)

The browser is still needed for checkout (multi-step form flow).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from .config import Booking

BASE_URL = "https://camping.bcparks.ca"

PARK_IDS = {
    "Garibaldi": {
        "transactionLocationId": -2147483602,
        "resourceLocationId": -2147483609,
        "mapId": -2147483578,
    },
}

CAMPSITE_RESOURCE_IDS = {
    "Garibaldi": {
        "Elfin Lakes": -2147481167,
        "Elfin Lakes Shelter": -2147481161,
        "Taylor Meadows": -2147481158,
        "Garibaldi Lake": -2147481156,
        "Cheakamus Lake": -2147481159,
        "Helm Creek": -2147481165,
        "Rampart Ponds": -2147481157,
        "Russet Lake": -2147481160,
        "Singing Creek": -2147481166,
        "Wedgemount": -2147481163,
        "Red Heather": -2147481164,
    },
}

BACKCOUNTRY_BOOKING_CATEGORY_ID = 4
BACKCOUNTRY_BOOKING_MODEL = 5
PEOPLE_CAPACITY_CATEGORY_ID = -32764
EQUIPMENT_CAPACITY_CATEGORY_ID = -32766
RATE_CATEGORY_ID = -32768
TERMINAL_LOCATION_ID = -2147483590

SUB_CAPACITY_IDS = {
    "adult": -32761,
    "youth": -32760,
    "child": -32759,
}


def _get_resource_id(park: str, campsite: str) -> int:
    park_sites = CAMPSITE_RESOURCE_IDS.get(park)
    if not park_sites:
        raise ValueError(f"Unknown park '{park}'. Known: {list(CAMPSITE_RESOURCE_IDS)}")
    rid = park_sites.get(campsite)
    if not rid:
        raise ValueError(f"Unknown campsite '{campsite}' in {park}. Known: {list(park_sites)}")
    return rid


def _build_cart_commit_payload(
    cart_data: dict,
    booking: Booking,
    resource_id: int,
) -> dict:
    cart_uid = cart_data["cartUid"]
    txn_uid = cart_data["createTransactionUid"]
    new_txn = cart_data["newTransaction"]

    booking_uid = str(uuid.uuid4())
    blocker_uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    park = PARK_IDS[booking.park]
    start_date = booking.arrival_date.isoformat()
    end_date = booking.departure_date.isoformat()

    return {
        "cart": {
            "cartUid": cart_uid,
            "createTransactionUid": txn_uid,
            "shopperUid": new_txn.get("shopperUid"),
            "groupUid": None,
            "referenceNumberPrefix": new_txn["referenceNumberPrefix"],
            "referenceNumberSuffix": new_txn["referenceNumberSuffix"],
            "newTransaction": {
                "cartTransactionUid": txn_uid,
                "cartUid": "00000000-0000-0000-0000-000000000000",
                "completeDate": None,
                "createDate": new_txn["createDate"],
                "editBookingLock": False,
                "lastEditDate": now,
                "referenceNumberPrefix": new_txn["referenceNumberPrefix"],
                "referenceNumberSuffix": new_txn["referenceNumberSuffix"],
                "shiftUid": new_txn["shiftUid"],
                "shopperUid": new_txn.get("shopperUid"),
                "status": 1,
                "terminalLocationId": TERMINAL_LOCATION_ID,
                "transactionBookings": [],
                "transactionSales": [],
                "transactionShipments": [],
                "userUid": new_txn["userUid"],
            },
            "transactionDrafts": [],
            "transactionHistory": [],
            "giftCards": [],
            "sales": [],
            "bookings": [
                {
                    "bookingUid": booking_uid,
                    "cartUid": cart_uid,
                    "bookingCategoryId": BACKCOUNTRY_BOOKING_CATEGORY_ID,
                    "bookingModel": BACKCOUNTRY_BOOKING_MODEL,
                    "newVersion": {
                        "cartTransactionUid": txn_uid,
                        "bookingMembers": [],
                        "bookingVehicles": [],
                        "bookingBoats": [],
                        "bookingCapacityCategoryCounts": [
                            {
                                "capacityCategoryId": PEOPLE_CAPACITY_CATEGORY_ID,
                                "subCapacityCategoryId": SUB_CAPACITY_IDS["adult"],
                                "count": booking.num_people,
                                "isAdult": True,
                            },
                            {
                                "capacityCategoryId": PEOPLE_CAPACITY_CATEGORY_ID,
                                "subCapacityCategoryId": SUB_CAPACITY_IDS["youth"],
                                "count": 0,
                                "isAdult": False,
                            },
                            {
                                "capacityCategoryId": PEOPLE_CAPACITY_CATEGORY_ID,
                                "subCapacityCategoryId": SUB_CAPACITY_IDS["child"],
                                "count": 0,
                                "isAdult": False,
                            },
                            {
                                "capacityCategoryId": EQUIPMENT_CAPACITY_CATEGORY_ID,
                                "subCapacityCategoryId": None,
                                "count": booking.num_tent_pads,
                            },
                        ],
                        "rateCategoryId": RATE_CATEGORY_ID,
                        "resourceBlockerUids": [],
                        "resourceNonSpecificBlockerUids": [],
                        "resourceZoneBlockerUids": [blocker_uid],
                        "resourceZoneEntryBlockerUids": [],
                        "startDate": start_date,
                        "endDate": end_date,
                        "releasePersonalInformation": False,
                        "equipmentCategoryId": None,
                        "subEquipmentCategoryId": None,
                        "occupant": {
                            "contact": {
                                "email": "",
                                "contactName": "",
                                "phoneNumberCountryCode": None,
                                "phoneNumber": "",
                            },
                            "address": {},
                            "allowMarketing": False,
                            "phoneNumbers": {},
                            "preferredCultureName": "en-CA",
                            "firstName": "",
                            "lastName": "",
                        },
                        "requiresCheckout": False,
                        "bookingStatus": 0,
                        "completedDate": new_txn["createDate"],
                        "arrivalComment": "",
                        "entryPointResourceId": None,
                        "exitPointResourceId": None,
                        "bookingSurcharges": [],
                        "consentToRelease": False,
                        "equipmentDescription": "",
                        "groupHoldUid": "",
                        "organizationName": "",
                        "passExpiryDate": None,
                        "passNumber": "",
                        "resourceLocationId": park["resourceLocationId"],
                        "checkInTime": None,
                        "checkOutTime": None,
                        "deferredPayment": False,
                    },
                    "createTransactionUid": txn_uid,
                    "currentVersion": None,
                    "history": [],
                    "drafts": [],
                    "referenceNumberPostfix": "",
                }
            ],
            "shipments": [],
            "groupHold": None,
            "paymentGroups": [],
            "gatewayPaymentSessions": [],
            "lineItems": [],
            "resourceBlockers": [],
            "resourceNonSpecificBlockers": [],
            "resourceZoneBlockers": [
                {
                    "blockerType": 0,
                    "cartUid": cart_uid,
                    "resourceZoneBlockerUid": blocker_uid,
                    "bookingUid": booking_uid,
                    "groupHoldUid": "",
                    "isReservation": True,
                    "newVersion": {
                        "creationDate": now,
                        "cartTransactionUid": txn_uid,
                        "startDate": start_date,
                        "endDate": end_date,
                        "resourceId": resource_id,
                        "resourceLocationId": park["resourceLocationId"],
                        "status": 0,
                        "unitsBlocked": booking.num_tent_pads,
                    },
                }
            ],
            "resourceZoneEntryBlockers": [],
            "waitlistApplications": [],
        }
    }


async def install_request_hook(page, log_fn=None):
    """Install JS hooks that capture all outgoing POST requests.

    Must be called via page.add_init_script() BEFORE navigation so the hooks
    are installed before Angular bootstraps.
    """
    await page.add_init_script("""
    window.__capturedPosts = [];

    // Hook fetch
    const _origFetch = window.fetch;
    window.fetch = async function(...args) {
        const [url, opts] = args;
        if (opts && opts.method && opts.method.toUpperCase() === 'POST' && opts.body) {
            window.__capturedPosts.push({
                type: 'fetch',
                url: typeof url === 'string' ? url : url.url,
                body: opts.body
            });
        }
        return _origFetch.apply(this, args);
    };

    // Hook XMLHttpRequest
    const _origXHROpen = XMLHttpRequest.prototype.open;
    const _origXHRSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
        this.__hookUrl = url;
        this.__hookMethod = method;
        return _origXHROpen.call(this, method, url, ...rest);
    };
    XMLHttpRequest.prototype.send = function(body) {
        if (this.__hookMethod && this.__hookMethod.toUpperCase() === 'POST' && body) {
            window.__capturedPosts.push({
                type: 'xhr',
                url: this.__hookUrl,
                body: typeof body === 'string' ? body : JSON.stringify(body)
            });
        }
        return _origXHRSend.call(this, body);
    };
    """)


async def get_captured_requests(page) -> list:
    """Retrieve all captured POST requests from the page."""
    return await page.evaluate("() => window.__capturedPosts || []")


async def api_add_to_cart(page, booking: Booking, log_fn=None) -> dict:
    """Add campsite to cart via fetch() calls inside the browser page.

    Runs JavaScript fetch() so all cookies/headers are inherited automatically.
    Two API calls: GET /api/cart → POST /api/cart/commit.
    """
    _log = log_fn or (lambda x: None)

    resource_id = _get_resource_id(booking.park, booking.campsite)
    _log(f"API mode: {booking.campsite} (resource {resource_id})")

    park = PARK_IDS[booking.park]
    start_date = booking.arrival_date.isoformat()
    end_date = booking.departure_date.isoformat()

    js_code = """
    async ([resourceId, resourceLocationId, startDate, endDate, numPeople, numTentPads]) => {
        const cartResp = await fetch('/api/cart');
        if (!cartResp.ok) return { error: 'cart_fetch', status: cartResp.status, text: await cartResp.text() };
        const cart = await cartResp.json();

        const cartUid = cart.cartUid;
        const txnUid = cart.createTransactionUid;
        const newTxn = cart.newTransaction;
        const shopper = cart.shopper;
        const shopperData = shopper && shopper.currentVersion ? shopper.currentVersion : null;

        const bookingUid = crypto.randomUUID();
        const blockerUid = crypto.randomUUID();
        const now = new Date().toISOString();

        const occupant = {
            contact: { email: "", contactName: "", phoneNumberCountryCode: null, phoneNumber: "" },
            address: {},
            allowMarketing: false,
            phoneNumbers: {},
            preferredCultureName: shopperData ? shopperData.preferredCultureName || "en-CA" : "en-CA",
            firstName: shopperData ? shopperData.firstName || "" : "",
            lastName: shopperData ? shopperData.lastName || "" : "",
        };

        const payload = {
            cart: {
                ...cart,
                newTransaction: {
                    ...newTxn,
                    cartTransactionUid: txnUid,
                    cartUid: "00000000-0000-0000-0000-000000000000",
                    lastEditDate: now,
                    status: 1,
                },
                bookings: [{
                    bookingUid: bookingUid,
                    cartUid: cartUid,
                    bookingCategoryId: 4,
                    bookingModel: 5,
                    newVersion: {
                        cartTransactionUid: txnUid,
                        bookingMembers: [],
                        bookingVehicles: [],
                        bookingBoats: [],
                        bookingCapacityCategoryCounts: [
                            { capacityCategoryId: -32764, subCapacityCategoryId: -32761, count: numPeople, isAdult: true },
                            { capacityCategoryId: -32764, subCapacityCategoryId: -32760, count: 0, isAdult: false },
                            { capacityCategoryId: -32764, subCapacityCategoryId: -32759, count: 0, isAdult: false },
                            { capacityCategoryId: -32766, subCapacityCategoryId: null, count: numTentPads }
                        ],
                        rateCategoryId: -32768,
                        resourceBlockerUids: [],
                        resourceNonSpecificBlockerUids: [],
                        resourceZoneBlockerUids: [blockerUid],
                        resourceZoneEntryBlockerUids: [],
                        startDate: startDate,
                        endDate: endDate,
                        releasePersonalInformation: false,
                        equipmentCategoryId: null,
                        subEquipmentCategoryId: null,
                        occupant: occupant,
                        requiresCheckout: false,
                        bookingStatus: 0,
                        completedDate: now,
                        arrivalComment: "",
                        entryPointResourceId: null,
                        exitPointResourceId: null,
                        bookingSurcharges: [],
                        consentToRelease: false,
                        equipmentDescription: "",
                        groupHoldUid: "",
                        organizationName: "",
                        passExpiryDate: null,
                        passNumber: "",
                        resourceLocationId: resourceLocationId,
                        checkInTime: null,
                        checkOutTime: null,
                        deferredPayment: false,
                    },
                    createTransactionUid: txnUid,
                    currentVersion: null,
                    history: [],
                    drafts: [],
                    referenceNumberPostfix: ""
                }],
                resourceZoneBlockers: [{
                    blockerType: 0,
                    cartUid: cartUid,
                    resourceZoneBlockerUid: blockerUid,
                    bookingUid: bookingUid,
                    groupHoldUid: "",
                    isReservation: true,
                    newVersion: {
                        creationDate: now,
                        cartTransactionUid: txnUid,
                        startDate: startDate,
                        endDate: endDate,
                        resourceId: resourceId,
                        resourceLocationId: resourceLocationId,
                        status: 0,
                        unitsBlocked: numTentPads,
                    },
                }],
                resourceZoneEntryBlockers: [],
                resourceBlockers: [],
                resourceNonSpecificBlockers: [],
            }
        };

        const commitResp = await fetch('/api/cart/commit?isCompleted=false&isSelfCheckIn=false', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const respText = await commitResp.text();
        if (!commitResp.ok) return {
            error: 'cart_commit',
            status: commitResp.status,
            text: respText.substring(0, 500),
        };

        return { success: true, bookingUid: bookingUid };
    }
    """

    result = await page.evaluate(
        js_code,
        [resource_id, park["resourceLocationId"], start_date, end_date,
         booking.num_people, booking.num_tent_pads],
    )

    if isinstance(result, dict) and result.get("error"):
        # Dump debug info to file for analysis
        from pathlib import Path
        debug_path = Path.home() / ".bc-camping-bot" / "api_debug.json"
        try:
            debug_path.write_text(json.dumps(result, indent=2))
            _log(f"Debug info saved to {debug_path}")
        except Exception:
            pass
        raise Exception(f"API {result['error']}: HTTP {result.get('status')} — {result.get('text', '')[:200]}")

    _log("Cart committed!")
    return result
