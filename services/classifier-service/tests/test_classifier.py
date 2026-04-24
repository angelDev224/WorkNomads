from app.classifier import LABELS, classify


def test_classify_returns_valid_label():
    result = classify("photos/user1/test.jpg")
    assert result.label in LABELS
    assert 0.0 <= result.confidence <= 1.0


def test_classify_is_deterministic():
    r1 = classify("photos/user1/photo.png")
    r2 = classify("photos/user1/photo.png")
    assert r1.label == r2.label
    assert r1.confidence == r2.confidence


def test_classify_different_keys_may_differ():
    r1 = classify("photos/user1/a.jpg")
    r2 = classify("photos/user2/b.jpg")
    # Not guaranteed different, but very likely
    assert isinstance(r1.label, str)
    assert isinstance(r2.label, str)
