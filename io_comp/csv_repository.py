"""
Layer 2 – CSV Repository Implementation

Concrete implementation of ICalendarRepository that loads events from a
comma-separated-values file.  The file path is *injected* via the
constructor so this class never hard-codes a location – keeping it
testable and reusable in different deployment contexts.

Expected CSV format (no header row):
    Person name, Event subject, Event start time, Event end time

Example row::
    Alice,"Morning meeting",08:00,09:30
"""

import csv
import logging
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List

from io_comp.exceptions import CalendarFileNotFoundError, InvalidEventError
from io_comp.models import Event
from io_comp.repository_interface import ICalendarRepository

logger = logging.getLogger(__name__)

# Fallback tz when a person has no entry in the tz_map.
_HOST_TZ = datetime.now(timezone.utc).astimezone().tzinfo


class CSVCalendarRepository:
    """Loads calendar :class:`Event` objects from a CSV file.

    Each person's times are normalised to UTC using **their own timezone**
    looked up from *tz_map*.  Persons not present in the map fall back to
    *default_tz* (host system offset when omitted).

    Args:
        filepath:    Absolute or relative path to the calendar CSV.
        tz_map:      Mapping of person name -> tzinfo.  Persons absent from
                     the map use *default_tz*.
        default_tz:  Fallback tzinfo.  Defaults to the host UTC offset.

    Raises:
        FileNotFoundError: If *filepath* does not exist.
    """

    def __init__(self, filepath: str, tz_map: Dict[str, Any] = None, default_tz=None) -> None:
        self._tz_map: Dict[str, Any] = tz_map or {}
        self._default_tz = default_tz or _HOST_TZ
        self._events: List[Event] = []
        self._load(filepath)

    # ------------------------------------------------------------------
    # ICalendarRepository implementation
    # ------------------------------------------------------------------

    def get_events(self, person_list: List[str]) -> List[Event]:
        """Return events belonging to any person in *person_list*.

        Filters in-memory here; a DB-backed implementation would push
        the equivalent ``WHERE person IN (...)`` to the database.

        Args:
            person_list: Names of the people whose events are needed.

        Returns:
            A filtered copy so callers cannot mutate the internal list.
        """
        person_set = set(person_list)
        return [e for e in self._events if e.person in person_set]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _to_utc(self, time_str: str, person: str) -> datetime:
        """Parse HH:MM, combine with today in *person*'s timezone, return UTC."""
        t = time.fromisoformat(time_str.strip())
        tz = self._tz_map.get(person, self._default_tz)
        local_dt = datetime.combine(date.today(), t, tzinfo=tz)
        return local_dt.astimezone(timezone.utc)

    def _load(self, filepath: str) -> None:
        """Parse the CSV file and populate ``self._events``.

        Malformed rows (fewer than 4 columns) are skipped with a warning.
        Time values are normalised to UTC via :meth:`_to_utc`.
        """
        try:
            with open(filepath, newline="", encoding="utf-8") as fh:
                for line_num, row in enumerate(csv.reader(fh), start=1):
                    if len(row) < 4:
                        logger.warning(
                            "Skipping malformed row %d in '%s': %r",
                            line_num, filepath, row,
                        )
                        continue
                    try:
                        person = row[0].strip()
                        event = Event(
                            person=person,
                            subject=row[1].strip().strip('"'),
                            start=self._to_utc(row[2], person),
                            end=self._to_utc(row[3], person),
                        )
                        self._events.append(event)
                    except ValueError as exc:
                        err = InvalidEventError(str(exc), line_num=line_num, filepath=filepath)
                        logger.error(str(err))
                        raise err from exc
        except FileNotFoundError:
            err = CalendarFileNotFoundError(filepath)
            logger.error(str(err))
            raise err
