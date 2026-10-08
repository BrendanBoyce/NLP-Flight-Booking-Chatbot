from dataclasses import dataclass
import csv
import re
from typing import List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

@dataclass
class QA_hit:       #represents the most likely answer returned
    qid: str
    question: str
    answer: str
    score: float

def _content_tokens(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z]{2,}", text.lower())

class QARetriever:
    def __init__(self, csv_path: str, *,
                 id_col: str = "QuestionID",
                 question_col: str = "Question",
                 answer_col: str = "Answer"):
        self.qids, self.questions, self.answers = [], [], []
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self.qids.append(row.get(id_col, ""))
                self.questions.append(row[question_col])
                self.answers.append(row[answer_col])

        # Vectorizers for questions and answers (1–2 grams)
        self.q_vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.a_vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))

        self.q_mat = self.q_vec.fit_transform(self.questions)
        self.a_mat = self.a_vec.fit_transform(self.answers)


    def answer(self, user_text: str, top_k: int = 5) -> QA_hit:
        # Stage 1: retrieve by question similarity
        q = self.q_vec.transform([user_text])
        q_sims = cosine_similarity(q, self.q_mat)[0]

        k = min(top_k, len(self.questions))
        cand_idx = np.argsort(-q_sims)[:k]

        # light tokeniser
        def toks(s):
            return re.findall(r"[a-zA-Z]{2,}", s.lower())

        q_terms = set(toks(user_text))

        # represent query in answer space as well
        a = self.a_vec.transform([user_text])

        best = None
        for i in cand_idx:
            # base sims
            q_sim = float(q_sims[i])
            a_sim = float(cosine_similarity(a, self.a_mat[i]).ravel()[0])

            # keyword overlaps
            ans_terms = set(toks(self.answers[i]))
            que_terms = set(toks(self.questions[i]))

            # coverage and extra for question, weighting
            q_coverage = (len(q_terms & que_terms) / max(1, len(q_terms))) if q_terms else 0.0
            q_extra = (len(que_terms - q_terms) / max(1, len(que_terms))) if que_terms else 0.0

            # coverage and extra for  answer, weighting
            a_coverage = (len(q_terms & ans_terms) / max(1, len(q_terms))) if q_terms else 0.0
            a_extra = (len(ans_terms - q_terms) / max(1, len(ans_terms))) if ans_terms else 0.0

            # blended score, tuning weights as needed
            score = (
                    0.45 * q_sim +
                    0.20 * a_sim +
                    0.15 * a_coverage +
                    0.10 * q_coverage -
                    0.06 * q_extra -
                    0.04 * a_extra
            )

            if (best is None) or (score > best[0]):
                best = (score, i)

        best_score, best_i = best
        return QA_hit(
            qid=self.qids[best_i],
            question=self.questions[best_i],
            answer=self.answers[best_i],
            score=best_score,
        )

