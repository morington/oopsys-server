from oopsys_server.domain.fingerprint import compute_fingerprint, normalize_message


def test_normalize_strips_numbers_and_uuids():
    a = normalize_message("user 12345 failed at /var/log/app.py")
    b = normalize_message("user 99 failed at /tmp/other.py")
    assert a == b


def test_normalize_strips_uuid():
    text = normalize_message("missing 550e8400-e29b-41d4-a716-446655440000 record")
    assert "<uuid>" in text


def test_same_logical_error_same_fingerprint():
    fp1 = compute_fingerprint(service="svc", exception_type="ValueError", message="bad value 1")
    fp2 = compute_fingerprint(service="svc", exception_type="ValueError", message="bad value 2")
    assert fp1 == fp2


def test_different_service_different_fingerprint():
    fp1 = compute_fingerprint(service="a", exception_type="ValueError", message="x")
    fp2 = compute_fingerprint(service="b", exception_type="ValueError", message="x")
    assert fp1 != fp2


def test_fingerprint_is_hex_sha256():
    fp = compute_fingerprint(service="s", exception_type="E", message="m")
    assert len(fp) == 64
    int(fp, 16)
