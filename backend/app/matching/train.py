"""Trains the matching encoder and exports it as plain NumPy artifacts.

Run manually (or on a schedule) to retrain as real usage data accumulates:

    cd backend && python -m app.matching.train

TensorFlow is only a training-time dependency (see requirements-train.txt).
The exported artifacts (vocab.json + weights.npz) are loaded by
app/matching/infer.py using pure NumPy, so the deployed API never imports
TensorFlow — keeping it off the memory-constrained production container.
"""

import asyncio
import json
import logging
import random
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow import keras

from app.matching.data import build_pairs, fetch_training_jobs
from app.matching.model import InBatchContrastiveModel, build_encoder, build_vectorizer
from app.matching.store import fetch_events, fetch_resume_scans

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
SEED = 42
EPOCHS = 12
BATCH_SIZE = 32


def _augment_with_usage_events(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Folds in real (anonymized) usage data collected since the last training run."""
    events = fetch_events()
    added = 0
    for event in events:
        if not event["skills"] or not event["job_title"]:
            continue
        anchor = f"{event['resume_title'] or ''} skills: {', '.join(event['skills'])}".strip()
        positive = f"{event['job_title']} at {event['job_company']}".strip()
        if len(anchor) > 5 and len(positive) > 5:
            pairs.append((anchor, positive))
            added += 1
    logger.info("Folded in %d real usage events (out of %d logged).", added, len(events))
    return pairs


def _augment_with_resume_scans(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Folds in real (anonymized) resume scans, independent of whether the
    user went on to search jobs. Title and skill-list are two views of the
    same real profile — same self-supervised structure as the job-posting
    bootstrap (title vs. description), just from the resume side instead."""
    scans = fetch_resume_scans()
    added = 0
    for scan in scans:
        if not scan["skills"] or not scan["title"]:
            continue
        anchor = scan["title"].strip()
        positive = f"skills: {', '.join(scan['skills'])}"
        if len(anchor) > 2 and len(positive) > 10:
            pairs.append((anchor, positive))
            added += 1
    logger.info("Folded in %d real resume scans (out of %d logged).", added, len(scans))
    return pairs


async def main():
    random.seed(SEED)
    tf.random.set_seed(SEED)

    logger.info("Fetching live job postings across %d bootstrap queries...", 16)
    jobs = await fetch_training_jobs()
    logger.info("Fetched %d unique real job postings.", len(jobs))

    pairs = build_pairs(jobs)
    pairs = _augment_with_usage_events(pairs)
    pairs = _augment_with_resume_scans(pairs)
    random.shuffle(pairs)
    logger.info("Training on %d (anchor, positive) pairs.", len(pairs))

    if len(pairs) < BATCH_SIZE:
        raise SystemExit(
            f"Only {len(pairs)} training pairs available, need at least {BATCH_SIZE}. "
            "Check network access to the job-board APIs."
        )

    anchors = np.array([p[0] for p in pairs])
    positives = np.array([p[1] for p in pairs])

    vectorizer = build_vectorizer(list(anchors) + list(positives))
    encoder = build_encoder(vectorizer)
    training_model = InBatchContrastiveModel(encoder)
    training_model.compile(optimizer=keras.optimizers.Adam(learning_rate=1e-3))

    dataset = tf.data.Dataset.from_tensor_slices((anchors, positives))
    dataset = dataset.shuffle(len(pairs), seed=SEED).batch(BATCH_SIZE, drop_remainder=True)

    history = training_model.fit(dataset, epochs=EPOCHS, verbose=2)
    final_acc = history.history["in_batch_accuracy"][-1]
    logger.info("Final in-batch retrieval accuracy: %.3f", final_acc)

    export(vectorizer, encoder, corpus_size=len(pairs), final_accuracy=float(final_acc))


def export(vectorizer, encoder, corpus_size: int, final_accuracy: float) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    vocab = vectorizer.get_vocabulary()
    embedding = encoder.get_layer("token_embedding").get_weights()[0]
    hidden_kernel, hidden_bias = encoder.get_layer("hidden").get_weights()
    proj_kernel, proj_bias = encoder.get_layer("projection").get_weights()

    np.savez(
        ARTIFACTS_DIR / "weights.npz",
        embedding=embedding,
        hidden_kernel=hidden_kernel,
        hidden_bias=hidden_bias,
        proj_kernel=proj_kernel,
        proj_bias=proj_bias,
    )
    (ARTIFACTS_DIR / "vocab.json").write_text(json.dumps(vocab), encoding="utf-8")
    (ARTIFACTS_DIR / "metadata.json").write_text(
        json.dumps({
            "corpus_size": corpus_size,
            "final_in_batch_accuracy": final_accuracy,
            "sequence_length": 64,
            "embedding_dim": embedding.shape[1],
        }),
        encoding="utf-8",
    )
    logger.info("Exported artifacts to %s", ARTIFACTS_DIR)


if __name__ == "__main__":
    asyncio.run(main())
