"""
App entry point – Composition Root

All dependency wiring is done here.  Every other layer (models, repository,
service) is unaware of concrete partners; they communicate only through
the interfaces defined in their own modules.

Timezone handling
-----------------
The host system's local UTC offset is detected at startup.  The repository
normalises CSV times to UTC; the service returns results in local time.
If no shared slot ≥ 30 minutes is found, a Groq AI suggestion is requested.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from io_comp import CSVCalendarRepository, CalendarService
from io_comp.ai_advisor import suggest_meeting_to_move
from io_comp.config import MIN_SLOT_MINUTES
from io_comp.repository_interface import ICalendarRepository
from io_comp.service_interface import ICalendarService

_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "calendar.log")

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),  # write to file                            # also show in terminal
    ],
)
logger = logging.getLogger(__name__)

# Output timezone: slots are printed in the caller's local time.
_OUTPUT_TZ = datetime.now(timezone.utc).astimezone().tzinfo
_AI_THRESHOLD = timedelta(minutes=MIN_SLOT_MINUTES)


def _parse_persons(raw: str) -> Tuple[List[str], Dict[str, object]]:
    """Parse 'Alice:Europe/London, Jack:America/New_York' into (names, tz_map).

    Names without a colon use the host's local timezone.
    Unknown timezone strings fall back to the host tz with a printed warning.
    """
    persons: List[str] = []
    tz_map: Dict[str, object] = {}
    for entry in (e.strip() for e in raw.split(",") if e.strip()):
        if ":" in entry:
            name, tz_str = entry.split(":", 1)
            name, tz_str = name.strip(), tz_str.strip()
            try:
                tz_map[name] = ZoneInfo(tz_str)
            except (ZoneInfoNotFoundError, KeyError):
                logger.warning("Unknown timezone '%s' for %s – using local tz.", tz_str, name)
                tz_map[name] = _OUTPUT_TZ
        else:
            name = entry
            tz_map[name] = _OUTPUT_TZ
        persons.append(name)
    return persons, tz_map


def run(
    service: ICalendarService,
    persons: List[str],
    tz_map: Dict[str, object],
) -> None:
    """Execute the scheduling query using an already-constructed service.

    This function contains only business logic and I/O presentation.
    It never constructs any dependency itself – they are all received
    via parameters (Dependency Injection), making it fully testable
    without touching the filesystem or stdin.

    Args:
        service: A fully constructed :class:`CalendarService` instance.
        persons: Names of all required attendees.
        tz_map:  Mapping of person name -> tzinfo for working-hour enforcement.
    """
    slots = service.sort_available_slots(persons, tz_map=tz_map)

    for name in persons:
        tz_label = str(tz_map.get(name, _OUTPUT_TZ))
        print(f"  {name} ({tz_label})")

    if slots:
        print("Free slots (most recommended first)-not to block a big brakest slot, but to show all options,times in your local tz:")
        for start, end in slots:
            duration = int((end - start).total_seconds() // 60)
            print(f"  {start.strftime('%H:%M')} - {end.strftime('%H:%M')}  ({duration} min)")
    else:
        print("  (no free slots)")

    # AI fallback: if no slot is >= 30 minutes, ask Groq for rescheduling advice.
    # Slots are sorted by duration ascending, so the last one is the longest.
    has_viable_slot = bool(slots) and (slots[-1][1] - slots[-1][0]) >= _AI_THRESHOLD
    if not has_viable_slot:
        blocking = service.get_blocking_events(persons)
        print(suggest_meeting_to_move(blocking, persons, _OUTPUT_TZ))


def main() -> None:
    """Composition root – wire all dependencies and delegate to run()."""
    csv_path = os.path.join(
        os.path.dirname(__file__), "..", "resources", "calendar.csv"
    )

    print("Enter persons with their timezone (timezone is optional).")
    print("  Examples: Alice:Europe/London, Jack:America/New_York")
    print("            Alice, Jack          (uses your local timezone)")
    raw = input("> ")
    persons, tz_map = _parse_persons(raw)
    if not persons:
        logger.warning("No valid names provided; exiting.")
        return

    repository: ICalendarRepository = CSVCalendarRepository(
        csv_path, tz_map=tz_map, default_tz=_OUTPUT_TZ
    )
    service = CalendarService(repository, output_tz=_OUTPUT_TZ)

    run(service, persons, tz_map)


if __name__ == "__main__":
    main()
