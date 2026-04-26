"""Load and validate booking configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml


@dataclass
class Booking:
    name: str
    park: str
    campsite: str
    arrival_date: date
    num_nights: int
    num_people: int
    num_tent_pads: int
    equipment_type: str
    session_file: str
    booking_date: date | None = None

    @property
    def booking_opens_at(self) -> datetime:
        """The booking window opens at 7:00 AM PT on the configured booking_date."""
        open_date = self.booking_date or (self.arrival_date - timedelta(days=91))
        return datetime(open_date.year, open_date.month, open_date.day, 7, 0, 0)

    @property
    def departure_date(self) -> date:
        return self.arrival_date + timedelta(days=self.num_nights)


def load_config(config_path: str) -> list[Booking]:
    path = Path(config_path)
    data = yaml.safe_load(path.read_text())

    bookings = []
    for entry in data["bookings"]:
        arrival = entry["arrival_date"]
        if isinstance(arrival, str):
            arrival = date.fromisoformat(arrival)

        bookings.append(
            Booking(
                name=entry["name"],
                park=entry["park"],
                campsite=entry.get("campsite", "any"),
                arrival_date=arrival,
                num_nights=entry.get("num_nights", 1),
                num_people=entry.get("num_people", 1),
                num_tent_pads=entry.get("num_tent_pads", 1),
                equipment_type=entry.get("equipment_type", "tent"),
                session_file=entry["session_file"],
                booking_date=date.fromisoformat(entry["booking_date"]) if entry.get("booking_date") else None,
            )
        )

    return bookings
