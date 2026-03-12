"""
AI Advisor – Groq-backed fallback for over-booked schedules.

When no shared free slot of 30+ minutes can be found deterministically,
this module sends the full list of blocking meetings to a Groq LLM and
asks which meeting looks most flexible or lowest-priority to reschedule.

The AI only *suggests* – it never modifies calendar data.

Requires the environment variable ``GROQ_API_KEY`` to be set.
"""

import logging
import os
from pathlib import Path
from typing import List

from io_comp.models import Event

# Load .env from the project root (three levels up from this file:
# io_comp/ → python-project/ → calendar_project/).
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(_ENV_FILE)
except ImportError:
    pass  # dotenv not installed; fall back to real environment variables

logger = logging.getLogger(__name__)

_MIN_SLOT_MINUTES = 30
_GROQ_MODEL = "llama-3.3-70b-versatile"


def suggest_meeting_to_move(
    blocking_events: List[Event],
    person_list: List[str],
    local_tz,
) -> str:
    """Ask Groq which blocking meeting should be rescheduled.

    Triggered when the Sweep Line algorithm finds no shared free slot of
    30+ minutes for all requested attendees.

    Args:
        blocking_events: All calendar events belonging to the requested
                         attendees (the meetings causing the conflict).
        person_list:     Names of the required attendees (for AI context).
        local_tz:        tzinfo used to format event times in the prompt
                         and response (should match what the user sees).

    Returns:
        A formatted string with the AI's recommendation, or an error/
        warning notice if the Groq package is missing or the API call fails.
    """
    # Lazy import: groq is only needed when the AI fallback is triggered.
    try:
        from groq import Groq
    except ImportError:
        return (
            "\n[!] 'groq' package not installed.\n"
            "   Run:  pip install groq\n"
            "   Then set the GROQ_API_KEY environment variable and try again."
        )

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return (
            "\n[!] GROQ_API_KEY environment variable is not set.\n"
            "   Export it and re-run to receive an AI scheduling suggestion."
        )

    persons_str = ", ".join(person_list)

    if blocking_events:
        events_lines = "\n".join(
            f"  • [{e.person}] \"{e.subject}\"  "
            f"{e.start.astimezone(local_tz).strftime('%H:%M')} – "
            f"{e.end.astimezone(local_tz).strftime('%H:%M')}  "
            f"({int((e.end - e.start).total_seconds() // 60)} min)"
            for e in sorted(blocking_events, key=lambda e: e.start)
        )
   
    system_instruction = """\
## Role
You are a smart scheduling assistant helping a team find a shared meeting time.

## Your Task
1. **Review** each meeting carefully.
2. **Identify** the ONE meeting that looks most flexible or lowest priority to reschedule.  
   Consider: short/generic titles, back-to-back stacking, internal vs. external meetings, and total duration.
3. **Recommend** moving that specific meeting and suggest a **concrete alternative time slot**  
   (e.g. _"move it to 19:00–19:30"_ or _"shift it to tomorrow morning"_).
4. **Explain** what free window this move would open up for the new 30-minute appointment.
5. **Summarise** your advice briefly, in a friendly and actionable tone.

> Address the team directly. Be concise and practical.
"""

    user_message = f"""\
## Required Attendees
{persons_str}

## Problem
The scheduling algorithm found **no shared free slot of {_MIN_SLOT_MINUTES}+ minutes** \
between 07:00 and 19:00 for all attendees today.

## Blocking Meetings (local time)
{events_lines}
"""

    try:
        import httpx
        from groq import Groq
        # Corporate SSL proxies intercept TLS with a self-signed cert that
        # Python's ssl module rejects.  Passing a custom httpx client with
        # verify=False bypasses the SSL chain check for the Groq API only.
        http_client = httpx.Client(verify=False)
        client = Groq(api_key=api_key, http_client=http_client)
        response = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user",   "content": user_message},
            ],
        )
        suggestion = response.choices[0].message.content.strip()
        divider = "-" * 62
        return (
            f"\n[AI] No {_MIN_SLOT_MINUTES}-minute slot found."
            f"  Here is what the AI recommends:\n"
            f"{divider}\n"
            f"{suggestion}\n"
            f"{divider}"
        )
    except Exception as exc:
        logger.error("Groq API call failed: %s", exc)
        return f"\n[!] AI suggestion failed: {exc}"
