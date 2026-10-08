from dataclasses import dataclass
import csv
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

@dataclass
class IntentHit:    #top intent after user input
    iid: str
    label: str
    score: float

class IntentRouter:                 #intent classifier using TF-IDF and cosine similarity
    def __init__(self, csv_path: str, *,
                 text_col: str = "sentence",
                 label_col: str = "label",
                 id_col: str = "IID",
                 min_confidence: float = 0.30):
        self.iids, self.texts, self.labels = [], [], []     #load intent samples from csv
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self.iids.append(row.get(id_col, ""))
                self.texts.append(row[text_col])
                self.labels.append(row[label_col])

        self.vec = TfidfVectorizer(stop_words=None, ngram_range=(1, 2))     #fitting TF-IDF over sentences using unigrams and bigrams
        self.mat = self.vec.fit_transform(self.texts)
        self.min_conf = float(min_confidence)       #min similarity that is acceptable label

    def predict(self, user_text: str) -> IntentHit:
        if not user_text.strip():                   #predict most similar intent example and return its label
            return IntentHit(iid="", label="unknown", score=0.0)
        q = self.vec.transform([user_text])
        sims = cosine_similarity(q, self.mat)[0]
        i = int(np.argmax(sims))
        score = float(sims[i])
        label = self.labels[i] if score >= self.min_conf else "unknown"
        return IntentHit(iid=self.iids[i], label=label, score=score)
