"""Unit tests for the cryptographic utilities module."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from app.services.crypto import (
    build_event_canonical_payload,
    did_to_public_key_hex,
    generate_keypair,
    is_timestamp_fresh,
    private_key_to_hex,
    public_key_to_did,
    public_key_to_hex,
    sha256_hex,
    sign_payload,
    verify_signature,
)


class TestKeypairGeneration:
    def test_generates_distinct_keypairs(self):
        _, pk1 = generate_keypair()
        _, pk2 = generate_keypair()
        assert public_key_to_hex(pk1) != public_key_to_hex(pk2)

    def test_public_key_hex_length(self):
        _, pk = generate_keypair()
        assert len(public_key_to_hex(pk)) == 64  # 32 bytes = 64 hex chars

    def test_private_key_hex_length(self):
        priv, _ = generate_keypair()
        assert len(private_key_to_hex(priv)) == 64


class TestDIDDerivation:
    def test_did_format(self):
        _, pk = generate_keypair()
        did = public_key_to_did(pk)
        assert did.startswith("did:key:z")

    def test_did_round_trip(self):
        """DID → public key hex → DID must be idempotent."""
        _, pk = generate_keypair()
        did = public_key_to_did(pk)
        recovered_hex = did_to_public_key_hex(did)
        assert recovered_hex == public_key_to_hex(pk)

    def test_invalid_did_raises(self):
        with pytest.raises(ValueError):
            did_to_public_key_hex("did:web:example.com")

    def test_did_uniqueness(self):
        dids = {public_key_to_did(generate_keypair()[1]) for _ in range(20)}
        assert len(dids) == 20


class TestSignatureVerification:
    def test_valid_signature(self):
        priv, pub = generate_keypair()
        msg = b"test message"
        sig = sign_payload(msg, private_key_to_hex(priv))
        assert verify_signature(msg, sig, public_key_to_hex(pub))

    def test_tampered_payload_fails(self):
        priv, pub = generate_keypair()
        sig = sign_payload(b"original", private_key_to_hex(priv))
        assert not verify_signature(b"tampered", sig, public_key_to_hex(pub))

    def test_wrong_key_fails(self):
        priv, pub = generate_keypair()
        _, other_pub = generate_keypair()
        sig = sign_payload(b"message", private_key_to_hex(priv))
        assert not verify_signature(b"message", sig, public_key_to_hex(other_pub))

    def test_corrupted_signature_fails(self):
        priv, pub = generate_keypair()
        sig = sign_payload(b"msg", private_key_to_hex(priv))
        corrupted = sig[:-4] + "XXXX"
        assert not verify_signature(b"msg", corrupted, public_key_to_hex(pub))

    def test_empty_payload(self):
        priv, pub = generate_keypair()
        sig = sign_payload(b"", private_key_to_hex(priv))
        assert verify_signature(b"", sig, public_key_to_hex(pub))


class TestCanonicalPayload:
    def test_deterministic_ordering(self):
        """Dict with different insertion order must produce identical bytes."""
        a = build_event_canonical_payload("t1", "EXTRACTION", "did1",
                                          datetime(2024, 1, 1, tzinfo=timezone.utc),
                                          {"z": 1, "a": 2})
        b = build_event_canonical_payload("t1", "EXTRACTION", "did1",
                                          datetime(2024, 1, 1, tzinfo=timezone.utc),
                                          {"a": 2, "z": 1})
        assert a == b

    def test_different_payloads_differ(self):
        a = build_event_canonical_payload("t1", "EXTRACTION", "did1",
                                          datetime(2024, 1, 1, tzinfo=timezone.utc), {})
        b = build_event_canonical_payload("t2", "ASSEMBLY", "did2",
                                          datetime(2024, 1, 2, tzinfo=timezone.utc), {})
        assert a != b


class TestTimestampFreshness:
    def test_fresh_timestamp(self):
        ts = datetime.now(tz=timezone.utc)
        assert is_timestamp_fresh(ts)

    def test_stale_timestamp(self):
        ts = datetime.now(tz=timezone.utc) - timedelta(seconds=400)
        assert not is_timestamp_fresh(ts)

    def test_future_timestamp_rejected(self):
        ts = datetime.now(tz=timezone.utc) + timedelta(seconds=400)
        assert not is_timestamp_fresh(ts)

    def test_borderline_timestamp(self):
        ts = datetime.now(tz=timezone.utc) - timedelta(seconds=290)
        assert is_timestamp_fresh(ts)  # within the 300 s window
