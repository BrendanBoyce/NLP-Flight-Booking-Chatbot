import csv
from collections import defaultdict

from booking_retrieval import BookingExampleRetriever
from handle_flight import FlightDatabase
from booking import BookingTransaction

FLIGHTS_CSV = "data/flight.csv"
TIMES_CSV = "data/times.csv"

def load_examples(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def eval_retrieval(example_inputs):
    retriever = BookingExampleRetriever(FLIGHTS_CSV)
    correct = 0

    for ex in example_inputs:
        sug = retriever.suggest(ex["utterance"])
        if not sug:
            continue

        gold = (
            ex.get("departure_city"),
            ex.get("arrival_city"),
        )
        pred = (
            sug.slots.get("departure_city"),
            sug.slots.get("arrival_city"),
        )

        if gold == pred:
            correct += 1

    print("\n[Retrieval]")
    print(f"Recall: {correct / len(example_inputs):.2f}")


def eval_slot_filling(example_inputs, flight_db):
    correct = defaultdict(int)
    total = defaultdict(int)
    exact = 0

    for ex in example_inputs:
        bt = BookingTransaction(flight_db=flight_db, example_retriever=None)
        bt._fill_slots_from_text(ex["utterance"])

        ok = True
        for slot in ["departure_city", "arrival_city", "departure_date", "departure_time"]:
            gold = ex.get(slot) or None
            pred = bt.state.slots.get(slot)
            total[slot] += 1
            if gold == pred:
                correct[slot] += 1
            else:
                ok = False

        if ok:
            exact += 1

    print("\n[Slot Filling]")
    for s in total:
        print(f"{s}: {correct[s] / total[s]:.2f}")
    print(f"Exact match: {exact / len(example_inputs):.2f}")


def eval_route_time_validity(example_inputs, flight_db):
    route_ok = time_ok = time_total = 0

    for ex in example_inputs:
        dep = ex.get("departure_city")
        arr = ex.get("arrival_city")
        t = ex.get("departure_time")

        if dep and arr and flight_db.route_exists(dep, arr):
            route_ok += 1
            if t:
                time_total += 1
                if t in flight_db.times_for_route(dep, arr):
                    time_ok += 1

    print("\n[Database Validity]")
    print(f"Valid routes: {route_ok / len(example_inputs):.2f}")
    if time_total:
        print(f"Valid times: {time_ok / time_total:.2f}")


if __name__ == "__main__":
    example_inputs = load_examples(FLIGHTS_CSV)
    db = FlightDatabase(TIMES_CSV)

    eval_retrieval(example_inputs)
    eval_slot_filling(example_inputs, db)
    eval_route_time_validity(example_inputs, db)
