from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta


from handle_flight import FlightDatabase
from booking_retrieval import BookingExampleRetriever

@dataclass
class BookingState:         #holds the state of booking transaction
    task_name: str
    required_slots: List[str]
    optional_slots: List[str]
    slots: Dict[str, Optional[str]] = field(default_factory=dict)
    state: str = "collecting"
    awaiting_passenger_number: bool = False  # set when we know it's plural but don't know how many
    last_route_dep: Optional[str] = None
    last_route_arr: Optional[str] = None
    bad_arr_streak: int = 0
    bad_dep_streak: int = 0
    last_unknown_city: Optional[str] = None
    unknown_city_streak: int = 0


class BookingTransaction:


    def __init__(self, schema_path: Optional[str] = None,
                 flight_db=None,
                 example_retriever=None):
        schema = self._load_schema(schema_path)
        required = schema.get("required_slots", [])
        optional = schema.get("optional_slots", [])

        slots = {name: None for name in required + optional}
        if "passengers" in slots:
            slots["passengers"] = "1"       #set passenger number to 1

        self.state = BookingState(
            task_name=schema.get("task_name", "book_flight"),
            required_slots=required,
            optional_slots=optional,
            slots=slots,
        )

        # dependencies
        self.flight_db = flight_db
        self.example_retriever = example_retriever

        # if flight_db provides cities, optionally override known cities
        if self.flight_db is not None:
            try:
                self.KNOWN_CITIES = self.flight_db.known_cities()
            except Exception:
                pass

    def exit_transaction(self, low: str) -> bool:                           #Logic for handling exit or help for user in transaction stage
        return any(k in low for k in ["exit", "quit", "stop", "cancel", "never mind", "nevermind"])

    def help_transaction(self, low: str) -> bool:
        return "help" in low or "what can you do" in low or "what now" in low

    def restart_transaction(self, low: str) -> bool:
        return any(k in low for k in ["start over", "restart", "reset"])

    def is_finished(self) -> bool:
        return self.state.state in {"completed", "cancelled"}

    def handle_input(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return "Sorry, I didn’t catch that. Could you rephrase?"

        low = text.lower()

        if self.exit_transaction(low):              #print statements for users if they ask for help or to exit durint booking transaction
            self.state.state = "cancelled"
            return "Okay — I’ve cancelled this booking. If you want to start again, say 'book a flight'."

        if self.restart_transaction(low):
            self._reset_slots()
            self.state.state = "collecting"
            return "Okay — I’ve reset the booking. Where are you flying from?"

        if self.help_transaction(low):
            return (
                "I can help you book a flight. Tell me your departure city, destination, date, and a departure time. "
                "You can also say 'cancel' to stop."
            )

        # Finished or cancelled
        if self.state.state == "completed":
            return "Your booking is already completed. If you want another one, say 'book a new flight'."
        if self.state.state == "cancelled":
            return "This booking was cancelled. Say 'book a flight' to start again."

        # Confirmation
        if self.state.state == "confirming":
            return self._handle_confirmation_response(text)


        if self.flight_db is not None:
            # where can i fly to from london
            m = re.search(r"\bwhere can i fly to from\s+([a-zA-Z\s]+)\b", low)
            if not m:
                m = re.search(r"\bwhere can i fly from\s+([a-zA-Z\s]+)\b", low)

            if m:
                dep_raw = m.group(1).strip()
                dep_city = self._match_known_city(dep_raw)
                if not dep_city:
                    return "I don’t recognise that departure city. Which city are you leaving from?"

                dests = self.flight_db.destinations_from(dep_city.title())
                if not dests:
                    return f"I don’t have any destinations listed from {dep_city.title()}."

                preview = ", ".join(dests[:10])
                more = "" if len(dests) <= 10 else f" (and {len(dests) - 10} more)"
                return f"From {dep_city.title()}, you can fly to: {preview}{more}."

            # help for users to find information about flight dates
            if (
                    "what dates" in low
                    or "available dates" in low
                    or "list dates" in low
                    or "show dates" in low
                    or low.strip() == "show list"
            ):
                return "You can travel on any date, except Sundays."

            # help for users to find information about flight times
            if any(kw in low for kw in ["what times", "available times", "list times", "show times"]):
                dep = self.state.slots.get("departure_city")
                arr = self.state.slots.get("arrival_city")
                if dep and arr:
                    times = self.flight_db.times_for_route(dep, arr)
                    if not times:
                        return f"I don’t have any scheduled times for flights from {dep} to {arr}."
                    return "Available departure times for this route are: " + ", ".join(times)
                return "Tell me your departure and arrival cities first, and I can list the available times."


        self._fill_slots_from_text(text)    #slot filling

        if self.state.awaiting_passenger_number:
            passengers = self._extract_passengers_number_only(low)
            if passengers:
                self.state.slots["passengers"] = passengers
                self.state.awaiting_passenger_number = False
            else:
                return "How many passengers should I book the tickets for?"


        dep = self.state.slots.get("departure_city")
        arr = self.state.slots.get("arrival_city")
        t = self.state.slots.get("departure_time")

        date_val = self.state.slots.get("departure_date")
        if date_val and not self._date_is_allowed(date_val):
            self.state.slots["departure_date"] = None
            return "We don’t operate flights on Sundays. Please choose another date."

        # unknown destination attempts: dep known, arr missing
        if self.flight_db is not None and dep and not arr:
            m_to = re.search(r"\bto\s+([a-zA-Z\s]+)\b", low)
            candidate = m_to.group(1).strip() if m_to else None

            if candidate is None and re.fullmatch(r"[a-zA-Z\s]+", low.strip()):
                candidate = low.strip()

            if candidate:
                cand_city = self._match_known_city(candidate)
                if not cand_city:
                    if not hasattr(self.state, "bad_arr_attempts"):
                        self.state.bad_arr_attempts = 0
                    self.state.bad_arr_attempts += 1

                    if self.state.bad_arr_attempts >= 2:
                        dests = self.flight_db.destinations_from(dep)
                        preview = ", ".join(dests[:10]) if dests else ""
                        more = "" if not dests or len(dests) <= 10 else f" (and {len(dests) - 10} more)"
                        return (
                            f"I don’t recognise '{candidate.title()}' as a valid destination from {dep}. "
                            f"From {dep}, you can fly to: {preview}{more}. "
                            f"Where would you like to fly to?"
                        )

        # route and time validation only when dep and arr exist
        if self.flight_db is not None and dep and arr:
            if not self.flight_db.route_exists(dep, arr):
                self.state.slots["arrival_city"] = None
                return (
                    f"Sorry — I don’t currently have any flights from {dep} to {arr}. "
                    f"Where would you like to fly to instead?"
                )

            if t:
                times = self.flight_db.times_for_route(dep, arr)
                if t not in times:
                    nearest = self.flight_db.nearest_times(dep, arr, t, k=2)
                    self.state.slots["departure_time"] = None
                    if nearest:
                        if len(nearest) == 1:
                            return f"We don’t have a flight at {t}. The closest time is {nearest[0]}. Which would you like?"
                        return f"We don’t have a flight at {t}. The closest times are {nearest[0]} and {nearest[1]}. Which one would you like?"
                    return f"We don’t have a flight at {t}. Available times are: " + ", ".join(times)

        # prompt missing slot
        missing = self._next_missing_required_slot()
        if missing:
            return self._prompt_for_missing_slot(missing)

        # enforce time before confirming
        if not self.state.slots.get("departure_time"):
            return "At what time would you like to travel?"

        self.state.state = "confirming"
        return self._confirmation_prompt()


    def _load_schema(self, schema_path: Optional[str]) -> Dict:     #loading json schema

        default_schema = {
            "task_name": "book_flight",
            "required_slots": ["departure_city", "arrival_city", "departure_date", "departure_time"],
            "optional_slots": ["passengers"],
        }

        if not schema_path:
            return default_schema

        if not os.path.exists(schema_path):
            return default_schema

        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "required_slots" in data:
                return data
            return default_schema
        except Exception:
            return default_schema

    def _next_missing_required_slot(self) -> Optional[str]:
        for name in self.state.required_slots:
            if not self.state.slots.get(name):
                return name
        return None




    def _fill_slots_from_text(self, text: str) -> None: #slot extraction
        low = text.lower()

        # Cities departure and arrival
        dep, arr, has_from, has_to = self._extract_cities(low)

        current_dep = self.state.slots.get("departure_city")
        current_arr = self.state.slots.get("arrival_city")

        if dep:
            if not current_dep:
                # No departure yet so use dep as departure
                self.state.slots["departure_city"] = dep.title()
                current_dep = self.state.slots["departure_city"]

            elif not current_arr and not arr and not has_from:
                self.state.slots["arrival_city"] = dep.title()
                current_arr = self.state.slots["arrival_city"]

        # Handle arr candidate
        if arr:
            if not current_arr:
                self.state.slots["arrival_city"] = arr.title()
                current_arr = self.state.slots["arrival_city"]
            elif not current_dep and not dep:
                self.state.slots["departure_city"] = arr.title()
                current_dep = self.state.slots["departure_city"]

        # date
        date = self._extract_date(low)
        if date and not self.state.slots.get("departure_date"):
            self.state.slots["departure_date"] = date

        # time
        time = self._extract_time(low)
        if time and not self.state.slots.get("departure_time"):
            self.state.slots["departure_time"] = time

        # passengers logic
        passengers, awaiting = self._extract_passengers(low)
        if passengers:
            self.state.slots["passengers"] = passengers
            self.state.awaiting_passenger_number = False
        elif awaiting:
            self.state.awaiting_passenger_number = True


        valid_cities = None
        if getattr(self, "flight_db", None) is not None:
            try:
                valid_cities = {c.lower() for c in self.flight_db.known_cities()}
            except Exception:
                valid_cities = None

        if self.example_retriever is not None:
            sug = self.example_retriever.suggest(text)
            if sug and sug.score >= 0.65:
                # only fill if still missing

                if not self.state.slots.get("departure_city") and sug.slots.get("departure_city"):
                    cand = sug.slots["departure_city"].strip()
                    if valid_cities is None or cand.lower() in valid_cities:
                        self.state.slots["departure_city"] = cand.title()

                if not self.state.slots.get("arrival_city") and sug.slots.get("arrival_city"):
                    cand = sug.slots["arrival_city"].strip()
                    if valid_cities is None or cand.lower() in valid_cities:
                        self.state.slots["arrival_city"] = cand.title()

                # Date and time can be hinted too
                if not self.state.slots.get("departure_date") and sug.slots.get("departure_date"):
                    self.state.slots["departure_date"] = sug.slots["departure_date"]

                if not self.state.slots.get("departure_time") and sug.slots.get("departure_time"):
                    self.state.slots["departure_time"] = sug.slots["departure_time"]

                if not self.state.slots.get("passengers") and sug.slots.get("passengers"):
                    self.state.slots["passengers"] = sug.slots["passengers"]

    def _extract_cities(self, text: str) -> (Optional[str], Optional[str], bool, bool):

        dep: Optional[str] = None
        arr: Optional[str] = None

        from_match = re.search(
            r"\bfrom\s+([a-zA-Z\s]+?)(?=\s+to\b|[,.!?;:]|$)", text
        )
        to_match = re.search(
            r"\bto\s+(?!from\b)([a-zA-Z\s]+?)(?=\s+from\b|[,.!?;:]|$)",
            text
        )

        has_from = from_match is not None
        has_to = to_match is not None

        _ = (                                               #no longer need print but may be useful
            f"[DEBUG] _extract_cities input: {text!r}, "
            f"from_match={from_match and from_match.group(1)!r}, "
            f"to_match={to_match and to_match.group(1)!r}"
        )

        if from_match:
            candidate = from_match.group(1).strip()
            city = self._match_known_city(candidate)
            if city:
                dep = city

        if to_match:
            candidate = to_match.group(1).strip()
            city = self._match_known_city(candidate)
            if city:
                arr = city


        if not has_from and not has_to:
            detected = [city for city in self.KNOWN_CITIES if city in text]

            if len(detected) == 1:
                dep = detected[0]
            elif len(detected) >= 2:
                dep = detected[0]
                arr = detected[1]

        return dep, arr, has_from, has_to

    def _match_known_city(self, fragment: str) -> Optional[str]:
        fragment = fragment.lower()
        fragment = re.split(r"[,.!?]", fragment)[0].strip()
        if not fragment:
            return None

        best_city = None
        best_pos = None
        best_len = -1

        for city in self.KNOWN_CITIES:
            pos = fragment.find(city)
            if pos == -1:
                continue
            if best_pos is None or pos < best_pos or (pos == best_pos and len(city) > best_len):
                best_city = city
                best_pos = pos
                best_len = len(city)

        return best_city

    def _extract_date(self, text: str) -> Optional[str]:

        low = (text or "").strip().lower()

        # Relative dates
        if re.fullmatch(r"(today|tomorrow)", low):
            return low

        # uk style DD/MM/YYYY
        m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", low)
        if m:
            dd = int(m.group(1))
            mm = int(m.group(2))
            yyyy = int(m.group(3))
            if 1 <= dd <= 31 and 1 <= mm <= 12:
                return f"{yyyy:04d}-{mm:02d}-{dd:02d}"

        wds = ["monday", "tuesday", "wednesday", "thursday",
               "friday", "saturday", "sunday"]

        m = re.fullmatch(r"(?:next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", low)
        if m:
            wd = m.group(1)
            return f"next {wd}"

        return None

    def _extract_time(self, text: str) -> Optional[str]:

        # explicit hours and minutes
        m = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2))
            if 0 <= hh < 24 and 0 <= mm < 60:
                return f"{hh:02d}:{mm:02d}"

        # patterns like 9am or 9 am
        m = re.search(r"\b(\d{1,2})\s*(am|pm)\b", text)
        if m:
            hh = int(m.group(1))
            ampm = m.group(2)
            if ampm == "pm" and hh < 12:
                hh += 12
            if ampm == "am" and hh == 12:
                hh = 0
            return f"{hh:02d}:00"

        # vague times
        if "morning" in text:
            return "09:00"
        if "afternoon" in text:
            return "13:00"
        if "evening" in text or "night" in text:
            return "18:00"

        return None

    def _extract_passengers(self, text: str) -> (Optional[str], bool):

        # explicit digit count
        m = re.search(r"\b(\d+)\s+(passengers?|people|tickets?|seats?)\b", text)
        if m:
            return m.group(1), False

        # plural indicators without explicit number
        plural_cues = ["tickets", "people", "us", "we", "all of us"]
        if any(cue in text for cue in plural_cues):
            return None, True

        return None, False

    def _extract_passengers_number_only(self, text: str) -> Optional[str]:

        m = re.search(r"\b(\d+)\b", text)
        if m:
            return m.group(1)
        return None


    def _prompt_for_missing_slot(self, slot_name: str) -> str:  #user prompts to gain more info for slots
        if slot_name == "departure_city":
            return "Where are you flying from?"
        if slot_name == "arrival_city":
            return "Where would you like to fly to?"
        if slot_name == "departure_date":
            return "On which date would you like to travel?"
        if slot_name == "departure_time":
            return "At what time would you like to travel?"
        return "Could you tell me more details?"

    def _confirmation_prompt(self) -> str:
        dep = self.state.slots.get("departure_city", "UNKNOWN")     #returns info to user
        arr = self.state.slots.get("arrival_city", "UNKNOWN")
        date = self.state.slots.get("departure_date", "UNKNOWN")
        time = self.state.slots.get("departure_time", "any time")
        passengers = self.state.slots.get("passengers", "1")

        return (
            f"Okay, just to confirm: you want to fly from {dep} to {arr} "
            f"on {date} at {time} for {passengers} passenger(s). Is that correct?"
        )

    def _handle_confirmation_response(self, text: str) -> str:
        low = text.lower()
        yes_words = {"yes", "yeah", "yep", "correct", "that’s right", "thats right", "sure"}
        no_words = {"no", "nope", "not really", "wrong"}

        if any(w in low for w in yes_words):
            self.state.state = "completed"
            return self._completion_message()
        if any(w in low for w in no_words):
            self._reset_slots()
            self.state.state = "collecting"
            return "Okay, let’s start again. Where are you flying from?"

        # In case of ambiguity
        return "Please answer yes or no: is the booking summary correct?"

    def _completion_message(self) -> str:
        dep = self.state.slots.get("departure_city", "UNKNOWN")
        arr = self.state.slots.get("arrival_city", "UNKNOWN")
        date = self.state.slots.get("departure_date", "UNKNOWN")
        time = self.state.slots.get("departure_time", "any time")
        passengers = self.state.slots.get("passengers", "1")
        return (
            f"Your flight from {dep} to {arr} on {date} at {time} "
            f"for {passengers} passenger(s) has been booked️!"
        )

    def _reset_slots(self) -> None:
        for name in self.state.required_slots + self.state.optional_slots:
            self.state.slots[name] = None
        if "passengers" in self.state.slots:
            self.state.slots["passengers"] = "1"
        self.state.awaiting_passenger_number = False


    def _resolve_date(self, date_str: str) -> Optional[date]:

        low = (date_str or "").strip().lower()
        today = date.today()

        if low == "today":
            return today
        if low == "tomorrow":
            return today + timedelta(days=1)

        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", low)
        if m:
            y, mo, d = map(int, m.groups())
            return date(y, mo, d)

        # "next <weekday>"
        m = re.fullmatch(r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", low)
        if m:
            target = m.group(1)
            wd_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            target_wd = wd_map[target]
            delta = (target_wd - today.weekday()) % 7
            if delta == 0:
                delta = 7
            return today + timedelta(days=delta)

        return None

    def _date_is_allowed(self, date_str: str) -> bool:  #for no flights on sundays
        resolved = self._resolve_date(date_str)
        if resolved is None:
            return True
        return resolved.weekday() != 6  # Sunday
