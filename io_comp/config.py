"""
Shared Application Configuration

Central place for constants used across multiple modules.
Import from here instead of re-defining magic numbers in each module.
"""

# Minimum meeting slot duration in minutes.
# Used by the service to decide when to call the AI fallback advisor.
MIN_SLOT_MINUTES: int = 30

# Working-day boundaries (wall-clock hour, minute) applied per person in their own timezone.
WORKING_START: tuple[int, int] = (7, 0)
WORKING_END:   tuple[int, int] = (19, 0)
