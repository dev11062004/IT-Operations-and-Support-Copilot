"""RAGAS metrics computation module with safe native fallback."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("RAGASEvaluator")

try:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import answer_correctness, answer_relevancy, answer_similarity
    from langchain_openai import ChatOpenAI
    answer_correctness.weights = [1, 0]  # pure factual correctness
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    logger.info("RAGAS library is not available. Using native evaluation fallback.")


class RAGASEvaluator:
    """Wrapper for RAGAS evaluation metrics with native fallback."""

    def __init__(self, model_name: str, api_key: str):
        """Initialize the RAGAS evaluator.
        
        Args:
            model_name: Name of the model to use for evaluation
            api_key: Model API key
        """
        self.model_name = model_name
        self.api_key = api_key

        if RAGAS_AVAILABLE:
            self.llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                temperature=0.0
            )
            self.metrics = [
                answer_relevancy,
                answer_similarity,
                answer_correctness
            ]
        else:
            self.llm = None
            self.metrics = []

    def evaluate_single(
        self,
        question: str,
        answer: str,
        ground_truth: str
    ) -> Dict[str, float]:
        """Evaluate a single question-answer pair.
        
        Args:
            question: The input question
            answer: The generated answer from the agent
            ground_truth: The reference/expected answer
            
        Returns:
            Dictionary with metric names and scores
        """
        if not RAGAS_AVAILABLE:
            from evaluation.metrics.generation import (
                compute_answer_correctness,
                compute_answer_relevancy,
            )
            rel = compute_answer_relevancy(question, answer)
            corr = compute_answer_correctness(answer, ground_truth)
            return {
                "answer_relevancy": rel,
                "answer_similarity": corr,
                "answer_correctness": corr
            }

        # Create a dataset with a single sample
        data = {
            "question": [question],
            "answer": [answer],
            "ground_truth": [ground_truth]
        }

        dataset = Dataset.from_dict(data)

        try:
            result = evaluate(
                dataset=dataset,
                metrics=self.metrics,
                llm=self.llm
            )

            def extract_scalar(value):
                if isinstance(value, list) and len(value) > 0:
                    value = value[0]
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            return {
                "answer_relevancy": extract_scalar(result["answer_relevancy"]),
                "answer_similarity": extract_scalar(result["answer_similarity"]),
                "answer_correctness": extract_scalar(result["answer_correctness"])
            }
        except Exception as e:
            return {
                "answer_relevancy": None,
                "answer_similarity": None,
                "answer_correctness": None,
                "error": str(e)
            }

    def evaluate_batch(
        self,
        questions: List[str],
        answers: List[str],
        ground_truths: List[str]
    ) -> Dict[str, List[float]]:
        """Evaluate a batch of question-answer pairs."""
        if not RAGAS_AVAILABLE:
            from evaluation.metrics.generation import (
                compute_answer_correctness,
                compute_answer_relevancy,
            )
            rel_list = [compute_answer_relevancy(q, a) for q, a in zip(questions, answers)]
            corr_list = [compute_answer_correctness(a, g) for a, g in zip(answers, ground_truths)]
            return {
                "answer_relevancy": rel_list,
                "answer_similarity": corr_list,
                "answer_correctness": corr_list
            }

        data = {
            "question": questions,
            "answer": answers,
            "ground_truth": ground_truths
        }
        dataset = Dataset.from_dict(data)
        return evaluate(
            dataset=dataset,
            metrics=self.metrics,
            llm=self.llm
        )
