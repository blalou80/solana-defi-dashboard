"""Input validation for user-supplied values (W1 wallet onboarding)."""

import re

from solders.pubkey import Pubkey

# base58 alphabet (Bitcoin/Solana variant)
_BASE58_RE = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}\Z")


def validate_solana_address(candidate: str) -> tuple[bool, str]:
    """Return ``(ok, reason)`` for a user-entered Solana address.

    Uses the real decoder (``solders.Pubkey.from_string``) — a string only
    passes if it is exactly 32 bytes of valid base58. Never accepts
    partials, whitespace, or lookalikes.
    """
    if candidate is None:
        return False, "Address is empty."
    text = candidate.strip()
    if not text:
        return False, "Address is empty."
    if not _BASE58_RE.match(text):
        return False, (
            "Not a valid base58 string (32–44 chars, no 0/O/I/l)."
        )
    try:
        Pubkey.from_string(text)
    except Exception:
        return False, "Address does not decode to a 32-byte public key."
    return True, text  # normalized (trimmed) address in `reason` on success
