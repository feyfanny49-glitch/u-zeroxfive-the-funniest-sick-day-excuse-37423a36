#!/usr/bin/env python3
"""The Funniest Sick-Day Excuse -- judged-text entrypoint (revised).

Writes exactly one line, under 200 characters, to /output/entry.txt.
The artifact is published atomically with mode 0644 and no trailing newline,
then read back and verified byte-for-byte against the local gate.
"""
from __future__ import annotations

import hashlib
import os
import stat
import sys
import tempfile

OUTPUT = "/output"
ARTIFACT = os.path.join(OUTPUT, "entry.txt")
TEMP_PREFIX = ".entry.txt."

# Final line: a real text to a boss, a fresh concrete mishap, and the
# deadpan escalation landing on the last word. Under the 200-char hard cap.
ENTRY = "Can't come in — I tried to fold a fitted sheet and now I'm filing for disability."


def validate(text: str) -> bytes:
    """Apply the gate locally: UTF-8, 1..200 chars, one non-blank line, no padding."""
    if not isinstance(text, str):
        raise ValueError("entry must be text")
    if not text.strip():
        raise ValueError("entry must not be only whitespace")
    if text != text.strip():
        raise ValueError("entry must not carry leading/trailing whitespace")
    if not 1 <= len(text) <= 200:
        raise ValueError(f"entry length {len(text)} is outside 1..200")
    if len(text.splitlines()) != 1:
        raise ValueError("entry must be exactly one line")
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text):
        raise ValueError("entry must not contain control characters")
    data = text.encode("utf-8")
    if data.decode("utf-8") != text:
        raise ValueError("entry must round-trip through UTF-8")
    return data


def write_atomically(data: bytes) -> None:
    """Remove stale temps, then publish the artifact via chmod(0644) + os.replace."""
    os.makedirs(OUTPUT, exist_ok=True)
    for name in os.listdir(OUTPUT):
        if name.startswith(TEMP_PREFIX):
            try:
                os.unlink(os.path.join(OUTPUT, name))
            except OSError:
                pass
    fd, tmp = tempfile.mkstemp(prefix=TEMP_PREFIX, dir=OUTPUT)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        # mkstemp creates 0600; the gate refuses it. Fix the mode BEFORE replace.
        os.chmod(tmp, 0o644)
        os.replace(tmp, ARTIFACT)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def verify(data: bytes) -> dict:
    """Re-read the published artifact and confirm every hard cap."""
    with open(ARTIFACT, "rb") as fh:
        published = fh.read()
    if published != data:
        raise SystemExit("artifact bytes differ from the intended entry")
    text = published.decode("utf-8")
    if not 1 <= len(text) <= 200 or not text.strip() or "\n" in text:
        raise SystemExit("artifact fails the 1..200 / non-blank / one-line gate")
    mode = stat.S_IMODE(os.stat(ARTIFACT).st_mode)
    if mode != 0o644:
        raise SystemExit(f"refused mode {oct(mode)} on {ARTIFACT}")
    listing = sorted(os.listdir(OUTPUT))
    if listing != ["entry.txt"]:
        raise SystemExit(f"/output must hold only entry.txt; found {listing}")
    return {
        "chars": len(text),
        "bytes": len(published),
        "mode": oct(mode),
        "sha256": hashlib.sha256(published).hexdigest(),
        "output": listing,
    }


def main() -> int:
    data = validate(ENTRY)
    write_atomically(data)
    info = verify(data)
    print(f"verified {ARTIFACT}: {info['chars']} chars, {info['bytes']} bytes, "
          f"mode {info['mode']}, sha256 {info['sha256']}, /output={info['output']}")
    print(ENTRY)
    return 0


if __name__ == "__main__":
    sys.exit(main())
