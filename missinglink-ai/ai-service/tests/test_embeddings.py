import numpy as np

from app.config import Settings
from app.providers.embeddings import EmbeddingService, cosine_similarity


def test_fallback_embedding_is_deterministic():
    svc = EmbeddingService(Settings())
    a = svc.text_embedding("red jacket near the river")
    b = svc.text_embedding("red jacket near the river")
    assert a.shape == (512,)
    assert np.allclose(a, b)


def test_image_and_text_fallbacks_are_comparable():
    svc = EmbeddingService(Settings())
    img = svc.fallback._build_basis()[:64].tobytes()  # arbitrary deterministic bytes
    e_img = svc.image_embedding(img)
    e_txt = svc.text_embedding("a")
    # both live in the same 512-d space and are unit norm
    assert abs(float(np.linalg.norm(e_img)) - 1.0) < 1e-4
    assert abs(float(np.linalg.norm(e_txt)) - 1.0) < 1e-4


def test_cosine_similarity_ranges():
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([0.0, 1.0, 0.0])
    assert abs(cosine_similarity(a, a) - 1.0) < 1e-9
    assert abs(cosine_similarity(a, b)) < 1e-9
    assert abs(cosine_similarity(a, -a) + 1.0) < 1e-9
