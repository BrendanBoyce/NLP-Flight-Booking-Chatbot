from __future__ import annotations
import csv
import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional, List
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class ExampleSuggestion:        #similar approach to intent matching
    score: float
    matched_input: str
    slots: Dict[str, str]


class BookingExampleRetriever:      #used to support slot extraction, cannot override explicit timetable flights

    def __init__(self, csv_path: str, *,
                 utterance_col: str = "utterance",      #utterance being input from database rather than user
                 slot_cols: Optional[List[str]] = None):
        if slot_cols is None:
            slot_cols = ["departure_city", "arrival_city", "departure_date", "departure_time", "passengers"]

        self.input: List[str] = []
        self.slot_rows: List[Dict[str, str]] = []

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if utterance_col not in (reader.fieldnames or []):
                raise ValueError(f"{csv_path} must contain column: {utterance_col}")

            for row in reader:
                utt = (row.get(utterance_col) or "").strip()
                if not utt:
                    continue

                slots: Dict[str, str] = {}
                for c in slot_cols:
                    val = (row.get(c) or "").strip()
                    if val:
                        slots[c] = val

                self.input.append(utt)
                self.slot_rows.append(slots)

        self.vec = TfidfVectorizer(ngram_range=(1, 2))
        self.mat = self.vec.fit_transform(self.input) if self.input else None

    def suggest(self, user_text: str):
        if self.mat is None or not user_text.strip():
            return None
        q = self.vec.transform([user_text])
        sims = cosine_similarity(q, self.mat)[0]
        i = int(np.argmax(sims))
        score = float(sims[i])
        return ExampleSuggestion(
            score=score,
            matched_input=self.input[i],
            slots=self.slot_rows[i],
        )
