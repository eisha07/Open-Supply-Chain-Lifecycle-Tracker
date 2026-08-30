"""
Cryptographic utilities for the Digital Product Passport system.

Implements:
  - Ed25519 keypair generation
  - DID (did:key) derivation from a public key
  - Canonical payload serialisation
  - Signature creation and verification
  - Replay-attack timestamp validation
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict

import base58
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from app.config import get_settings

settings = get_settings()

# Multicodec prefix for Ed25519 public keys (0xed01 → [0xed, 0x01])
_ED25519_MULTICODEC_PREFIX = bytes([0xED, 0x01])


# ─────────────────────────── Key Generation ─────────────────────────────────

def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Generate a fresh Ed25519 keypair."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def private_key_to_hex(private_key: Ed25519PrivateKey) -> str:
    """Serialise private key to a 64-char hex string (32-byte raw seed)."""
    raw = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    return raw.hex()


def public_key_to_hex(public_key: Ed25519PublicKey) -> str:
    """Serialise public key to a 64-char hex string."""
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return raw.hex()


def private_key_from_hex(hex_str: str) -> Ed25519PrivateKey:
    """Deserialise private key from hex string."""
    raw = bytes.fromhex(hex_str)
    return Ed25519PrivateKey.from_private_bytes(raw)


def public_key_from_hex(hex_str: str) -> Ed25519PublicKey:
    """Deserialise public key from hex string."""
    raw = bytes.fromhex(hex_str)
    return Ed25519PublicKey.from_public_bytes(raw)


# ─────────────────────────── DID Derivation ──────────────────────────────────

def public_key_to_did(public_key: Ed25519PublicKey) -> str:
    """
    Derive a did:key identifier from an Ed25519 public key.

    Format: did:key:z<base58btc(multicodec_prefix + raw_public_key_bytes)>
    """
    raw_bytes = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    prefixed = _ED25519_MULTICODEC_PREFIX + raw_bytes
    encoded = base58.b58encode(prefixed).decode("ascii")
    return f"did:key:z{encoded}"


def did_to_public_key_hex(did: str) -> str:
    """
    Extract the hex-encoded raw public key from a did:key DID.

    Raises ValueError if the DID is malformed or has an unsupported key type.
    """
    if not did.startswith("did:key:z"):
        raise ValueError(f"Unsupported DID method or format: {did!r}")
    encoded = did[len("did:key:z"):]
    prefixed = base58.b58decode(encoded)
    if not prefixed.startswith(_ED25519_MULTICODEC_PREFIX):
        raise ValueError("DID does not encode an Ed25519 key")
    raw = prefixed[len(_ED25519_MULTICODEC_PREFIX):]
    return raw.hex()


# ─────────────────────── Canonical Payload & Hashing ─────────────────────────

def build_canonical_payload(data: Dict[str, Any]) -> bytes:
    """
    Produce a deterministic UTF-8 byte representation of a dict.

    Keys are sorted; no whitespace; ensures the same dict always produces
    the same bytes regardless of Python dict insertion order.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return hex-encoded SHA-256 digest of data."""
    return hashlib.sha256(data).hexdigest()


# ──────────────────────── Signing & Verification ─────────────────────────────

def sign_payload(payload_bytes: bytes, private_key_hex: str) -> str:
    """
    Sign payload_bytes with the given private key.

    Returns: base64url-encoded signature string.
    """
    private_key = private_key_from_hex(private_key_hex)
    sig_bytes = private_key.sign(payload_bytes)
    return base64.urlsafe_b64encode(sig_bytes).decode("ascii").rstrip("=")


def verify_signature(
    payload_bytes: bytes,
    signature_b64: str,
    public_key_hex: str,
) -> bool:
    """
    Verify that signature_b64 is a valid Ed25519 signature over payload_bytes
    produced by the private key corresponding to public_key_hex.

    Returns False (rather than raising) on invalid signatures or bad inputs.
    """
    try:
        # Restore stripped padding
        padding = "=" * (-len(signature_b64) % 4)
        sig_bytes = base64.urlsafe_b64decode(signature_b64 + padding)
        public_key = public_key_from_hex(public_key_hex)
        public_key.verify(sig_bytes, payload_bytes)
        return True
    except (InvalidSignature, ValueError, Exception):
        return False


# ──────────────────────── Replay-Attack Guard ─────────────────────────────────

def is_timestamp_fresh(actor_timestamp: datetime) -> bool:
    """
    Return True if actor_timestamp is within the configured max-age window.

    The window is symmetric: we reject both future-dated (clock-skew > 60 s)
    and stale timestamps beyond SIGNATURE_MAX_AGE_SECONDS.
    """
    now = datetime.now(tz=timezone.utc)
    if actor_timestamp.tzinfo is None:
        actor_timestamp = actor_timestamp.replace(tzinfo=timezone.utc)
    delta = abs((now - actor_timestamp).total_seconds())
    return delta <= settings.SIGNATURE_MAX_AGE_SECONDS


# ──────────────────────── Event Payload Builder ──────────────────────────────

def build_event_canonical_payload(
    twin_id: str,
    event_type: str,
    actor_did: str,
    actor_timestamp: datetime,
    metadata_json: Dict[str, Any],
) -> bytes:
    """
    Build the canonical bytes that the actor must sign for an event submission.

    Field order is fixed to: twin_id, event_type, actor_did, actor_timestamp,
    metadata_json.  All fields are included so that changing any one of them
    invalidates the signature.
    """
    payload = {
        "twin_id": twin_id,
        "event_type": event_type,
        "actor_did": actor_did,
        "actor_timestamp": actor_timestamp.isoformat(),
        "metadata_json": metadata_json,
    }
    return build_canonical_payload(payload)
