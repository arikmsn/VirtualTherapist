"""AI input fingerprinting — deterministic SHA-256 hash of the inputs to an AI call.

Usage:
    fp = compute_fingerprint({"summaries": [...], "mode": "concise"}, version=1)
    if session.prep_input_fingerprint == fp:
        return cached_result  # inputs unchanged, skip AI call

The hash is computed over a canonical JSON encoding (keys sorted, no whitespace)
so that the same logical payload always produces the same fingerprint.
"""

import hashlib
import json
from typing import Any

# Bump this when the fingerprint schema changes (e.g. new fields added to inputs).
# A version mismatch forces cache invalidation regardless of hash equality.
FINGERPRINT_VERSION = 2


def compute_fingerprint(payload: Any) -> str:
    """Return a hex SHA-256 hash of *payload* serialised to canonical JSON."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
