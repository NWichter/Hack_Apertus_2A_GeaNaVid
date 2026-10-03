"""Optional dense retrieval with a small local multilingual embedding model (intfloat/multilingual-e5-small, MIT).

Needs the extra `dense` (fastembed, ONNX runtime, CPU). Embeddings are cached per booklet.
"""

import threading

import numpy as np

from .config import cache_dir

MODEL = "intfloat/multilingual-e5-small"
_LOCK = threading.RLock()
_MODEL = None


def _model():
    global _MODEL
    with _LOCK:
        if _MODEL is None:
            from fastembed import TextEmbedding
            from fastembed.common.model_description import ModelSource, PoolingType

            try:
                TextEmbedding.add_custom_model(
                    model=MODEL,
                    pooling=PoolingType.MEAN,
                    normalization=True,
                    sources=ModelSource(hf=MODEL),
                    dim=384,
                    model_file="onnx/model.onnx",
                    additional_files=["onnx/sentencepiece.bpe.model"],
                )
            except ValueError:
                pass
            _MODEL = TextEmbedding(MODEL, cache_dir=str(cache_dir() / "models"))
        return _MODEL


def booklet_matrix(booklet):
    path = cache_dir() / "emb" / f"{booklet.sha256[:20]}.e5s-v1.npy"
    if path.is_file():
        return np.load(path)
    texts = [f"passage: {c.heading} {c.text}"[:2000] for c in booklet.chunks]
    with _LOCK:
        mat = np.array(list(_model().embed(texts, batch_size=32)), dtype=np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, mat)
    return mat


def query_scores(booklet, queries):
    mat = booklet_matrix(booklet)
    with _LOCK:
        q = np.array(list(_model().embed([f"query: {x}" for x in queries])), dtype=np.float32)
    return (mat @ q.T).max(axis=1)
