"""Pure-NumPy inference for the matching encoder — no TensorFlow import.

Reimplements the trained Keras model's forward pass (tokenize -> embed ->
masked mean-pool -> dense -> dense -> L2-normalize) from the exported
weights.npz + vocab.json. This is what actually runs in production, so the
deployed API container never pays TensorFlow's memory cost.
"""

import json
import re
import string
from functools import lru_cache
from pathlib import Path

import numpy as np

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
SEQUENCE_LENGTH = 64
_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")


class MatchEncoder:
    def __init__(self, vocab: list[str], weights: dict):
        self.token_to_id = {token: i for i, token in enumerate(vocab)}
        self.unk_id = 1  # Keras TextVectorization convention: 0 = pad, 1 = [UNK]
        self.embedding = weights["embedding"]
        self.hidden_kernel = weights["hidden_kernel"]
        self.hidden_bias = weights["hidden_bias"]
        self.proj_kernel = weights["proj_kernel"]
        self.proj_bias = weights["proj_bias"]

    def _tokenize(self, text: str) -> list[int]:
        cleaned = _PUNCT_RE.sub("", text.lower())
        tokens = cleaned.split()[:SEQUENCE_LENGTH]
        ids = [self.token_to_id.get(tok, self.unk_id) for tok in tokens]
        ids += [0] * (SEQUENCE_LENGTH - len(ids))
        return ids

    def embed(self, text: str) -> np.ndarray:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        ids = np.array([self._tokenize(t) for t in texts])  # (batch, seq_len)
        mask = (ids != 0).astype(np.float32)  # (batch, seq_len)

        embedded = self.embedding[ids]  # (batch, seq_len, dim)
        masked_sum = (embedded * mask[:, :, None]).sum(axis=1)
        token_counts = np.clip(mask.sum(axis=1, keepdims=True), 1, None)
        pooled = masked_sum / token_counts  # (batch, dim)

        hidden = np.maximum(pooled @ self.hidden_kernel + self.hidden_bias, 0)
        projected = hidden @ self.proj_kernel + self.proj_bias
        norms = np.clip(np.linalg.norm(projected, axis=1, keepdims=True), 1e-8, None)
        return projected / norms


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


@lru_cache(maxsize=1)
def get_encoder() -> MatchEncoder | None:
    """Loads the trained encoder, or None if no one has run training yet."""
    vocab_path = ARTIFACTS_DIR / "vocab.json"
    weights_path = ARTIFACTS_DIR / "weights.npz"
    if not vocab_path.exists() or not weights_path.exists():
        return None

    vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
    weights = dict(np.load(weights_path))
    return MatchEncoder(vocab, weights)
