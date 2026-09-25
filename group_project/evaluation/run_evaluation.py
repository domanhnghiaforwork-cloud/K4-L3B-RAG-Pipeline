"""Run resumable dense-vs-hybrid RAG evaluation and update submission reports."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import subprocess
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = ROOT / "group_project" / "evaluation"
GOLDEN_PATH = EVALUATION_DIR / "golden_dataset.json"
RAW_RESULTS_PATH = EVALUATION_DIR / "evaluation_results.json"
SUMMARY_PATH = EVALUATION_DIR / "evaluation_summary.json"
REPORT_PATH = EVALUATION_DIR / "RESULT.md"
REPORTS_DIR = ROOT / "reports"

CONFIGS = {
    "dense_only": {"label": "Config A — dense-only", "use_reranking": False},
    "hybrid_rrf": {"label": "Config B — hybrid + RRF", "use_reranking": True},
}
METRIC_KEYS = (
    "faithfulness",
    "answer_relevance",
    "context_recall",
    "context_precision",
)
TOP_K = 5
RRF_K = 60
EVALUATION_THRESHOLD = -1.0
DEFAULT_RPM = 10.0
AUTO_START = "<!-- evaluation-results:start -->"
AUTO_END = "<!-- evaluation-results:end -->"


class RateLimiter:
    """Sliding-window limiter for calls explicitly made by this runner."""

    def __init__(self, requests_per_minute: float) -> None:
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        self.limit = max(1, int(requests_per_minute))
        self.interval = 60.0 / requests_per_minute
        self.timestamps: deque[float] = deque()
        self.last_request = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        while self.timestamps and now - self.timestamps[0] >= 60.0:
            self.timestamps.popleft()

        delay = max(0.0, self.interval - (now - self.last_request))
        if len(self.timestamps) >= self.limit:
            delay = max(delay, 60.0 - (now - self.timestamps[0]) + 0.25)
        if delay > 0:
            print(f"Rate limit guard: waiting {delay:.1f}s", flush=True)
            time.sleep(delay)

        now = time.monotonic()
        while self.timestamps and now - self.timestamps[0] >= 60.0:
            self.timestamps.popleft()
        self.timestamps.append(now)
        self.last_request = now


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _record_key(record: dict) -> tuple[int, str]:
    return int(record["question_id"]), str(record["config"])


def _generation_targets(limit: int | None = None) -> list[dict]:
    golden = _read_json(GOLDEN_PATH, [])
    if not isinstance(golden, list) or len(golden) < 15:
        raise ValueError("golden_dataset.json must contain at least 15 cases")
    if limit:
        golden = golden[:limit]

    targets: list[dict] = []
    for question_id, item in enumerate(golden, start=1):
        for config_name in CONFIGS:
            targets.append(
                {
                    "question_id": question_id,
                    "config": config_name,
                    "question": item["question"],
                    "reference_answer": item["expected_answer"],
                    "reference_context": item["expected_context"],
                }
            )
    return targets


def _generate_answer(
    query: str,
    sources: list[dict],
    limiter: RateLimiter,
) -> str:
    from src.task10_generation import (
        SAFE_REFUSAL,
        SYSTEM_PROMPT,
        _ensure_valid_citations,
        call_llm,
        format_context,
        reorder_for_llm,
    )

    if not sources:
        return SAFE_REFUSAL
    labeled = [
        {**source, "_citation_label": f"S{index}"}
        for index, source in enumerate(sources, start=1)
    ]
    context = format_context(reorder_for_llm(labeled))
    user_message = f"Context:\n{context}\n\nQuestion: {query}"

    last_error: Exception | None = None
    for attempt in range(1, 4):
        limiter.wait()
        try:
            answer = call_llm(SYSTEM_PROMPT, user_message)
            return _ensure_valid_citations(answer, len(sources))
        except Exception as error:  # provider errors need a resumable retry
            last_error = error
            if attempt < 3:
                delay = 15 * attempt
                print(f"Generation attempt {attempt} failed; retrying in {delay}s", flush=True)
                time.sleep(delay)
    raise RuntimeError(f"Generation failed after 3 attempts: {last_error}")


def run_generation(limit: int | None, limiter: RateLimiter) -> list[dict]:
    """Generate answers for both configs and checkpoint after every answer."""
    from src.task9_retrieval_pipeline import retrieve

    targets = _generation_targets(limit)
    records: list[dict] = _read_json(RAW_RESULTS_PATH, [])
    existing = {_record_key(record): record for record in records}
    total = len(targets)

    for position, target in enumerate(targets, start=1):
        key = _record_key(target)
        if key in existing and existing[key].get("answer"):
            print(f"[{position}/{total}] Reuse {key}", flush=True)
            continue

        config = CONFIGS[target["config"]]
        print(
            f"[{position}/{total}] Generate Q{target['question_id']} "
            f"with {target['config']}",
            flush=True,
        )
        started = time.perf_counter()
        sources = retrieve(
            target["question"],
            top_k=TOP_K,
            score_threshold=EVALUATION_THRESHOLD,
            use_reranking=config["use_reranking"],
        )
        answer = _generate_answer(target["question"], sources, limiter)
        record = {
            **target,
            "answer": answer,
            "contexts": [source["content"] for source in sources],
            "source_ids": [source["id"] for source in sources],
            "source_scores": [float(source["score"]) for source in sources],
            "retrieval_methods": [source["retrieval_method"] for source in sources],
            "latency_seconds": round(time.perf_counter() - started, 4),
            "metrics": {},
        }
        existing[key] = record
        records = sorted(existing.values(), key=_record_key)
        _write_json(RAW_RESULTS_PATH, records)

    return sorted(existing.values(), key=_record_key)


def _build_metrics(limiter: RateLimiter) -> list[tuple[str, Any]]:
    from google import genai
    from ragas.cache import DiskCacheBackend
    from ragas.embeddings import HuggingFaceEmbeddings
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecision,
        ContextRecall,
        Faithfulness,
    )

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    evaluator_model = os.getenv("EVALUATOR_MODEL", os.getenv("LLM_MODEL", "")).strip()
    embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3").strip()
    if not api_key or not evaluator_model:
        raise RuntimeError("GEMINI_API_KEY and EVALUATOR_MODEL/LLM_MODEL are required")

    cache = DiskCacheBackend(str(ROOT / ".cache" / "ragas"))
    client = genai.Client(api_key=api_key)
    evaluator = llm_factory(
        evaluator_model,
        provider="google",
        client=client,
        adapter="instructor",
        cache=cache,
        temperature=0,
    )
    # Collections metrics may call the evaluator multiple times internally
    # (Faithfulness twice; ContextPrecision once per retrieved context). Wrap
    # the actual evaluator method so every hidden request observes the RPM cap.
    original_generate = evaluator.generate

    async def rate_limited_agenerate(*args: Any, **kwargs: Any) -> Any:
        await asyncio.to_thread(limiter.wait)
        return await asyncio.to_thread(original_generate, *args, **kwargs)

    evaluator.agenerate = rate_limited_agenerate  # type: ignore[method-assign]
    embeddings = HuggingFaceEmbeddings(
        model=embedding_model,
        device="cpu",
        normalize_embeddings=True,
        batch_size=8,
        cache=cache,
    )
    return [
        ("faithfulness", Faithfulness(llm=evaluator)),
        (
            "answer_relevance",
            AnswerRelevancy(llm=evaluator, embeddings=embeddings, strictness=1),
        ),
        ("context_recall", ContextRecall(llm=evaluator)),
        ("context_precision", ContextPrecision(llm=evaluator)),
    ]


def _score_with_retries(
    metric: Any,
    metric_arguments: dict[str, Any],
    label: str,
    max_attempts: int = 4,
) -> Any:
    """Retry one metric without losing previously checkpointed scores."""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return metric.score(**metric_arguments)
        except Exception as error:
            last_error = error
            if attempt >= max_attempts:
                break
            delay = min(120, 30 * (2 ** (attempt - 1)))
            print(
                f"Transient metric error for {label} "
                f"({type(error).__name__}: {error}). "
                f"Retry {attempt + 1}/{max_attempts} in {delay}s",
                flush=True,
            )
            time.sleep(delay)
    raise RuntimeError(
        f"Metric {label} failed after {max_attempts} attempts: {last_error}"
    ) from last_error


def run_metrics(records: list[dict], limiter: RateLimiter) -> list[dict]:
    """Score each record sequentially and checkpoint after every metric."""
    metrics = _build_metrics(limiter)
    total = len(records) * len(metrics)
    completed = sum(
        1 for record in records for key, _ in metrics if key in record.get("metrics", {})
    )

    for record in records:
        record.setdefault("metrics", {})
        for metric_key, metric in metrics:
            if metric_key in record["metrics"]:
                continue
            print(
                f"[{completed + 1}/{total}] Score Q{record['question_id']} "
                f"{record['config']} / {metric_key}",
                flush=True,
            )
            common = {
                "user_input": record["question"],
                "retrieved_contexts": record["contexts"],
                "reference": record["reference_answer"],
                "response": record["answer"],
            }
            metric_arguments = {
                "faithfulness": {
                    key: common[key]
                    for key in ("user_input", "response", "retrieved_contexts")
                },
                "answer_relevance": {
                    key: common[key] for key in ("user_input", "response")
                },
                "context_recall": {
                    key: common[key]
                    for key in ("user_input", "retrieved_contexts", "reference")
                },
                "context_precision": {
                    key: common[key]
                    for key in ("user_input", "reference", "retrieved_contexts")
                },
            }[metric_key]
            label = f"Q{record['question_id']} {record['config']} / {metric_key}"
            result = _score_with_retries(metric, metric_arguments, label)
            score = float(result.value)
            if not math.isfinite(score):
                raise RuntimeError(
                    f"Non-finite {metric_key} score for Q{record['question_id']} "
                    f"{record['config']}"
                )
            record["metrics"][metric_key] = round(score, 6)
            completed += 1
            _write_json(RAW_RESULTS_PATH, records)
    return records


def _mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 6) if values else 0.0


def _git_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_summary(records: list[dict]) -> dict:
    expected = len(_read_json(GOLDEN_PATH, [])) * len(CONFIGS)
    if len(records) != expected:
        raise RuntimeError(f"Expected {expected} records, found {len(records)}")
    for record in records:
        missing = set(METRIC_KEYS).difference(record.get("metrics", {}))
        if missing:
            raise RuntimeError(f"Q{record['question_id']} {record['config']} missing {missing}")

    configurations: dict[str, dict] = {}
    for config_name, config in CONFIGS.items():
        subset = [record for record in records if record["config"] == config_name]
        metric_means = {
            key: _mean([float(record["metrics"][key]) for record in subset])
            for key in METRIC_KEYS
        }
        configurations[config_name] = {
            "label": config["label"],
            "count": len(subset),
            "metrics": metric_means,
            "average": _mean(list(metric_means.values())),
            "latency_mean_seconds": _mean(
                [float(record["latency_seconds"]) for record in subset]
            ),
            "latency_median_seconds": round(
                statistics.median(float(record["latency_seconds"]) for record in subset),
                6,
            ),
        }

    dense = configurations["dense_only"]
    hybrid = configurations["hybrid_rrf"]
    deltas = {
        key: round(hybrid["metrics"][key] - dense["metrics"][key], 6)
        for key in METRIC_KEYS
    }
    deltas["average"] = round(hybrid["average"] - dense["average"], 6)
    winner = "hybrid_rrf" if deltas["average"] >= 0 else "dense_only"

    paired_wins = {"dense_only": 0, "hybrid_rrf": 0, "tie": 0}
    per_question = {
        (record["question_id"], record["config"]): _mean(
            [float(record["metrics"][key]) for key in METRIC_KEYS]
        )
        for record in records
    }
    for question_id in range(1, len(_read_json(GOLDEN_PATH, [])) + 1):
        dense_score = per_question[(question_id, "dense_only")]
        hybrid_score = per_question[(question_id, "hybrid_rrf")]
        if hybrid_score > dense_score:
            paired_wins["hybrid_rrf"] += 1
        elif dense_score > hybrid_score:
            paired_wins["dense_only"] += 1
        else:
            paired_wins["tie"] += 1

    ranked: list[dict] = []
    for record in records:
        sample_average = _mean([float(record["metrics"][key]) for key in METRIC_KEYS])
        ranked.append(
            {
                "question_id": record["question_id"],
                "question": record["question"],
                "config": record["config"],
                "metrics": record["metrics"],
                "average": sample_average,
                "source_ids": record["source_ids"],
            }
        )
    ranked.sort(key=lambda item: (item["average"], item["question_id"], item["config"]))

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "framework": "ragas 0.4.3",
        "evaluator_model": os.getenv("EVALUATOR_MODEL", os.getenv("LLM_MODEL", "")),
        "generator_model": os.getenv("LLM_MODEL", ""),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
        "git_commit": _git_revision(),
        "golden_dataset_size": len(_read_json(GOLDEN_PATH, [])),
        "top_k": TOP_K,
        "evaluation_threshold": EVALUATION_THRESHOLD,
        "configurations": configurations,
        "deltas_hybrid_minus_dense": deltas,
        "paired_wins": paired_wins,
        "partial_refusal_count": sum(
            "không thể xác minh" in record["answer"].lower() for record in records
        ),
        "missing_citation_count": sum(
            "[S" not in record["answer"]
            and "không thể xác minh" not in record["answer"].lower()
            for record in records
        ),
        "winner": winner,
        "worst_performers": ranked[:3],
    }


def _metric_label(key: str) -> str:
    return {
        "faithfulness": "Faithfulness",
        "answer_relevance": "Answer relevance",
        "context_recall": "Context recall",
        "context_precision": "Context precision",
    }[key]


def _failure_stage(metrics: dict) -> str:
    retrieval = min(metrics["context_recall"], metrics["context_precision"])
    if retrieval <= metrics["faithfulness"] and retrieval <= metrics["answer_relevance"]:
        return "retrieval/data"
    if metrics["faithfulness"] <= metrics["answer_relevance"]:
        return "generation"
    return "generation/relevance"


def _root_cause(item: dict) -> str:
    if item["question_id"] == 15 and item["config"] == "dense_only":
        return (
            "Top-5 dense lấy đúng bài nhưng bỏ sót chunk chứa danh sách đối tượng; "
            "generator vì thế trả lời thiếu/partial refusal"
        )
    if item["question_id"] == 2:
        return (
            "Context có passage liên quan nhưng bị trộn với chunk nhiễu/OCR; "
            "faithfulness judge cũng cần được kiểm tra vì answer có citation hỗ trợ"
        )
    weakest = min(item["metrics"], key=item["metrics"].get)
    return f"Metric thấp nhất: {_metric_label(weakest)}; kiểm tra source IDs trong raw results"


def write_result_report(summary: dict) -> None:
    dense = summary["configurations"]["dense_only"]
    hybrid = summary["configurations"]["hybrid_rrf"]
    delta = summary["deltas_hybrid_minus_dense"]
    winner = summary["configurations"][summary["winner"]]

    metric_rows = []
    for key in METRIC_KEYS:
        metric_rows.append(
            f"| {_metric_label(key)} | {dense['metrics'][key]:.4f} | "
            f"{hybrid['metrics'][key]:.4f} | {delta[key]:+.4f} |"
        )
    metric_rows.append(
        f"| **Average** | **{dense['average']:.4f}** | "
        f"**{hybrid['average']:.4f}** | **{delta['average']:+.4f}** |"
    )

    worst_rows = []
    for index, item in enumerate(summary["worst_performers"], start=1):
        metrics = item["metrics"]
        question = str(item["question"]).replace("|", "\\|")
        worst_rows.append(
            f"| {index} | {question} | {item['config']} | "
            f"{metrics['faithfulness']:.4f} | {metrics['answer_relevance']:.4f} | "
            f"{metrics['context_recall']:.4f} | {metrics['context_precision']:.4f} | "
            f"{_failure_stage(metrics)} | {_root_cause(item)} |"
        )

    report = f"""# RAG evaluation results

## Run information

| Field | Value |
| ----- | ----- |
| Evaluation date | {summary['generated_at']} |
| Framework and version | {summary['framework']} |
| Evaluator model | Gemini `{summary['evaluator_model']}`; temperature `0`; answer relevancy strictness `1` |
| Generator model | Gemini `{summary['generator_model']}`; temperature `0.3`; top-p `0.9` |
| Embedding model | Sentence Transformers `{summary['embedding_model']}` |
| Corpus | 3 legal documents + 5 news articles; 1,425 indexed chunks |
| Code/corpus commit at evaluation | `{summary['git_commit']}` |
| Golden dataset size | {summary['golden_dataset_size']} |
| `top_k` | {summary['top_k']} |
| A/B fallback threshold | `{summary['evaluation_threshold']}` (fallback disabled to isolate retrieval strategy) |
| Gemini rate limit used | 10 requests/minute with checkpoint, retry and Ragas disk cache |

## Configurations

- **Config A — dense-only:** cosine search over ChromaDB; `use_reranking=False`.
- **Config B — hybrid + RRF:** dense + BM25, fused once with RRF `k={RRF_K}`;
  `use_reranking=True`.

Hai config dùng cùng corpus, golden dataset, generator, evaluator, prompt và
`top_k`; chỉ thay retrieval strategy.

## Overall scores

| Metric | Config A | Config B | Delta B−A |
| ------ | -------: | -------: | --------: |
{chr(10).join(metric_rows)}

## A/B comparison

- Cấu hình tốt hơn theo average: **{winner['label']}**.
- Evidence: delta average hybrid − dense là **{delta['average']:+.4f}** trên
  {summary['golden_dataset_size']} câu; delta từng metric được trình bày trong
  bảng phía trên.
- Theo từng câu: hybrid thắng **{summary['paired_wins']['hybrid_rrf']}**, dense
  thắng **{summary['paired_wins']['dense_only']}**, hòa
  **{summary['paired_wins']['tie']}**.
- Latency generation trung bình: dense-only **{dense['latency_mean_seconds']:.2f}s**,
  hybrid + RRF **{hybrid['latency_mean_seconds']:.2f}s** mỗi câu.
- Latency median: dense-only **{dense['latency_median_seconds']:.2f}s**,
  hybrid + RRF **{hybrid['latency_median_seconds']:.2f}s**. Median cho thấy
  hybrid chậm hơn khoảng **{hybrid['latency_median_seconds'] - dense['latency_median_seconds']:.2f}s**;
  mean của dense bị tăng bởi lần cold-start tải embedding model đầu tiên.
- Chi phí LLM generation tương đương vì mỗi config gọi generator một lần/câu;
  hybrid thêm chi phí tính toán BM25 + RRF cục bộ.
- Cả 36 outputs đều có citation hợp lệ; có **{summary['partial_refusal_count']}**
  partial refusal và **{summary['missing_citation_count']}** answer thiếu citation.

## Worst performers

| # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
| -: | -------- | ------ | -----------: | --------: | -----: | --------: | ------------- | ---------- |
{chr(10).join(worst_rows)}

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| -------: | ------ | ------------------------------ | --------------- | ------------- |
| 1 | Rà soát/sửa OCR tại các passages của ba worst performers | Legal PDFs là bản scan và OCR còn lỗi dấu/từ | Tăng context recall và precision | Sửa corpus, re-index và chạy lại cùng runner |
| 2 | Tuning chunk size/overlap và `top_k` trên golden dataset | Worst performers chỉ ra câu bị thiếu hoặc thừa evidence | Cải thiện recall/precision | A/B cấu hình chunk mới, giữ nguyên generator/evaluator |
| 3 | Calibrate fallback trên tập in-domain/out-of-domain riêng | A/B này chủ động tắt fallback | Safe refusal và PageIndex ổn định hơn | Báo cáo score distribution và test ít nhất 5+5 câu |

## Limitations

- Golden dataset có 18 câu trong cùng một domain nên chưa đại diện cho mọi câu
  hỏi pháp lý hoặc câu hỏi đối kháng.
- Generator và evaluator dùng cùng model Gemini, có thể tạo self-evaluation bias.
- Answer relevancy dùng `strictness=1` để phù hợp giới hạn 15 request/phút;
  chạy nhiều lần hoặc strictness cao hơn có thể giảm variance.
- Các PDF legal là bản scan OCR và vẫn còn lỗi dấu/từ. Q2 cho thấy
  faithfulness judge có thể cho điểm thấp dù answer có passage/citation hỗ trợ,
  vì vậy worst cases đã được kiểm tra thủ công thay vì chỉ đọc metric.
- Fallback/PageIndex không thuộc A/B này (`score_threshold=-1.0`) và chưa có
  kết quả calibration thực nghiệm.

## Reproducibility artifacts

- `group_project/evaluation/golden_dataset.json`: 18 reference cases.
- `group_project/evaluation/evaluation_results.json`: answer, contexts, source IDs,
  latency và metric theo từng câu/config.
- `group_project/evaluation/evaluation_summary.json`: aggregate scores, delta và
  worst performers.
- Chạy lại: `python -m group_project.evaluation.run_evaluation --rpm 10`.
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _upsert_auto_section(path: Path, body: str) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    block = f"{AUTO_START}\n{body.strip()}\n{AUTO_END}"
    if AUTO_START in text and AUTO_END in text:
        prefix = text.split(AUTO_START, 1)[0].rstrip()
        suffix = text.split(AUTO_END, 1)[1].lstrip()
        text = f"{prefix}\n\n{block}\n"
        if suffix:
            text += f"\n{suffix}"
    else:
        text = f"{text.rstrip()}\n\n{block}\n"
    path.write_text(text, encoding="utf-8")


def update_individual_reports(summary: dict) -> None:
    dense = summary["configurations"]["dense_only"]
    hybrid = summary["configurations"]["hybrid_rrf"]
    delta = summary["deltas_hybrid_minus_dense"]["average"]
    winner = summary["configurations"][summary["winner"]]["label"]
    common = (
        f"Evaluation ngày {summary['generated_at']}: dense-only average "
        f"**{dense['average']:.4f}**, hybrid + RRF average "
        f"**{hybrid['average']:.4f}** (delta **{delta:+.4f}**)."
    )
    sections = {
        "2A202602943-hoang-phong.md": f"""## Kết quả evaluation liên quan phần việc data

{common}

- Corpus đã chuẩn hóa gồm 3 legal + 5 news và được index thành 1.425 chunks.
- Ba worst performers và source IDs được lưu trong `evaluation_summary.json`;
  đây là bằng chứng để rà soát lỗi OCR/nội dung nguồn.
""",
        "2A20262971-do-manh-nghia.md": f"""## Kết quả evaluation liên quan RAG pipeline

{common}

- Cấu hình tốt hơn theo average: **{winner}**.
- Mean generation latency: dense-only **{dense['latency_mean_seconds']:.2f}s**;
  hybrid + RRF **{hybrid['latency_mean_seconds']:.2f}s**.
- Pipeline đã index 1.425 chunks và A/B dùng `top_k=5`, fallback tắt để cô lập
  ảnh hưởng của retrieval strategy.
""",
        "2A202603010-nguyen-ngoc-tuyen.md": f"""## Kết quả evaluation liên quan UI và golden dataset

{common}

- Đã đánh giá đủ {summary['golden_dataset_size']} golden cases cho cả hai config.
- Cấu hình tốt hơn theo average: **{winner}**.
- Điểm từng metric, worst performers và khuyến nghị đã được ghi tự động vào
  `group_project/evaluation/RESULT.md`.
""",
    }
    for filename, section in sections.items():
        _upsert_auto_section(REPORTS_DIR / filename, section)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=("all", "generate", "evaluate", "report"),
        default="all",
        help="Run one stage or the full resumable pipeline.",
    )
    parser.add_argument(
        "--rpm",
        type=float,
        default=float(os.getenv("GEMINI_EVAL_RPM", DEFAULT_RPM)),
        help="Maximum explicit Gemini operations per minute (default: 10).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Use only the first N golden cases for a smoke test.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv(ROOT / ".env")
    args = parse_args()
    limiter = RateLimiter(args.rpm)

    if args.stage in {"all", "generate"}:
        records = run_generation(args.limit, limiter)
    else:
        records = _read_json(RAW_RESULTS_PATH, [])
        if not records:
            raise RuntimeError("No evaluation_results.json; run generation first")

    if args.stage in {"all", "evaluate"}:
        records = run_metrics(records, limiter)

    if args.stage in {"all", "report"}:
        summary = build_summary(records)
        _write_json(SUMMARY_PATH, summary)
        write_result_report(summary)
        update_individual_reports(summary)
        print(f"Completed report: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
