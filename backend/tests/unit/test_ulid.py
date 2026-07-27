from app.core.ulid import extract_timestamp_ms, is_valid_ulid, new_ulid


def test_ulid_format_is_26_chars_crockford_base32():
    value = new_ulid()
    assert len(value) == 26
    assert is_valid_ulid(value)


def test_ulid_is_time_ordered():
    a = new_ulid(timestamp_ms=1_000_000)
    b = new_ulid(timestamp_ms=1_000_001)
    assert a < b


def test_ulid_same_timestamp_still_valid_and_unique():
    a = new_ulid(timestamp_ms=1_000_000)
    b = new_ulid(timestamp_ms=1_000_000)
    assert a != b
    assert a[:10] == b[:10]


def test_extract_timestamp_roundtrip():
    ts = 1_722_000_000_000
    value = new_ulid(timestamp_ms=ts)
    assert extract_timestamp_ms(value) == ts


def test_is_valid_ulid_rejects_bad_input():
    assert not is_valid_ulid("too-short")
    assert not is_valid_ulid("I" * 26)  # I 不在 Crockford Base32 字母表中
    assert not is_valid_ulid(12345)
