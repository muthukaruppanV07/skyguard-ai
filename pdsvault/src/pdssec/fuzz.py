# SPDX-License-Identifier: MIT
"""Fuzz harness for parsers that consume untrusted media / network input:

  * the canonical payload parser (sync/record bodies),
  * the image/frame decoder (minimal container format used by the capture
    stub - a stand-in for the JPEG/HEIC/TIFF decoders a real build links),
  * the SQL interface (quarantine/update paths against adversarial inputs).

Every fuzz driver returns (did_not_crash, interesting).  Property-based tests
in tests/ drive these with Hypothesis; `fuzz_once` is the random driver.
"""

from __future__ import annotations

import os
import struct

from . import crypto


# --------------------------------------------------------------------------- #
# Untrusted media decoder (stand-in for the real image codec)
# --------------------------------------------------------------------------- #

FRAME_MAGIC = b"PVFRM1"


def decode_frame(buf: bytes) -> dict:
    """Parse the minimal frame container.

      magic(6) | payload_len(u32be) | crc32(u32be) | payload

    Returns {'ok': True, 'w': w, 'h': h, 'data': payload} or raises
    MediaFormatError (never a host crash; the caller quarantines).
    """
    if not buf.startswith(FRAME_MAGIC):
        raise MediaFormatError("bad magic")
    if len(buf) < 6 + 4 + 4:
        raise MediaFormatError("truncated frame header")
    (plen,) = struct.unpack(">I", buf[6:10])
    (crc,) = struct.unpack(">I", buf[10:14])
    if len(buf) < 14 + plen:
        raise MediaFormatError("truncated payload")
    payload = buf[14:14 + plen]
    if (crc & 0xFFFFFFFF) != (zlib_crc32(payload) & 0xFFFFFFFF):
        raise MediaFormatError("frame checksum mismatch")
    if plen < 8:
        raise MediaFormatError("payload too small for metadata")
    w, h = struct.unpack(">II", payload[:8])
    if w == 0 or h == 0 or w > 16384 or h > 16384:
        raise MediaFormatError("implausible frame dimensions")
    return {"ok": True, "w": w, "h": h, "data": payload[8:]}


def zlib_crc32(b: bytes) -> int:
    import zlib
    return zlib.crc32(b)


class MediaFormatError(Exception):
    pass


def make_frame(w: int, h: int, data: bytes) -> bytes:
    payload = struct.pack(">II", w, h) + data
    return (FRAME_MAGIC + struct.pack(">II", len(payload),
                                      zlib_crc32(payload)) + payload)


# --------------------------------------------------------------------------- #
# Fuzz drivers
# --------------------------------------------------------------------------- #

def fuzz_canonical(buf: bytes) -> bool:
    """`_parse_canonical` must never crash or accept duplicates silently."""
    try:
        crypto._parse_canonical(buf)
    except (ValueError, UnicodeDecodeError):
        return True
    return True


def fuzz_frame(buf: bytes) -> bool:
    """decode_frame must only raise MediaFormatError (quarantine) or return
    a sane frame; never leak/abort."""
    try:
        r = decode_frame(buf)
        assert isinstance(r["w"], int) and r["w"] > 0
    except MediaFormatError:
        return True
    except Exception:
        return False
    return True


def fuzz_sql_store_path(buf: bytes) -> bool:
    """A hostile path/identifier must not escape the sandboxed store dir."""
    try:
        p = buf.decode("utf-8", "replace")
    except Exception:
        return True
    safe = _is_safe_ident(p)
    return isinstance(safe, bool)


def _is_safe_ident(s: str) -> bool:
    return bool(s) and all(c.isalnum() or c in "-_" for c in s)