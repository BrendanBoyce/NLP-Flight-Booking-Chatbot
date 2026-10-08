from __future__ import annotations
import csv
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional


def _time_to_minutes(t: str) -> Optional[int]:
    try:
        hh, mm = t.split(":")
        h = int(hh)
        m = int(mm)
        if 0 <= h < 24 and 0 <= m < 60:
            return h * 60 + m
    except Exception:
        pass
    return None


@dataclass(frozen=True)
class FlightKey:
    dep: str
    arr: str


class FlightDatabase:

    def __init__(self, csv_path: str):
        self._times: Dict[FlightKey, List[str]] = {}
        self._cities: set[str] = set()

        tmp: Dict[FlightKey, set[str]] = {}

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required_cols = {"departure_city", "arrival_city", "departure_time"}
            if not required_cols.issubset(set(reader.fieldnames or [])):
                raise ValueError(
                    f"{csv_path} must contain columns: departure_city, arrival_city, departure_time"
                )

            for row in reader:
                dep = (row["departure_city"] or "").strip().lower()
                arr = (row["arrival_city"] or "").strip().lower()
                t = (row["departure_time"] or "").strip()

                if not dep or not arr or not t:
                    continue

                if _time_to_minutes(t) is None:
                    continue

                key = FlightKey(dep=dep, arr=arr)
                tmp.setdefault(key, set()).add(t)

                self._cities.add(dep)
                self._cities.add(arr)

        # freeze into sorted lists
        for key, timeset in tmp.items():
            self._times[key] = sorted(timeset, key=lambda x: _time_to_minutes(x) or 0)

    def known_cities(self) -> set[str]:
        return set(self._cities)

    def route_exists(self, dep: str, arr: str) -> bool:
        return FlightKey(dep=dep.lower(), arr=arr.lower()) in self._times

    def times_for_route(self, dep: str, arr: str) -> List[str]:
        return self._times.get(FlightKey(dep=dep.lower(), arr=arr.lower()), [])

    def nearest_times(self, dep: str, arr: str, requested_time: str, k: int = 2) -> List[str]:
        times = self.times_for_route(dep, arr)
        req_m = _time_to_minutes(requested_time)
        if not times or req_m is None:
            return []

        scored: List[Tuple[int, str]] = []
        for t in times:
            m = _time_to_minutes(t)
            if m is not None:
                scored.append((abs(m - req_m), t))

        scored.sort(key=lambda x: x[0])
        return [t for _, t in scored[:k]]

    def destinations_from(self, dep: str) -> list[str]:
        dep = dep.lower()
        dests = sorted({k.arr.title() for k in self._times.keys() if k.dep == dep})
        return dests

    def departures_to(self, arr: str) -> list[str]:
        arr = arr.lower()
        deps = sorted({k.dep.title() for k in self._times.keys() if k.arr == arr})
        return deps
