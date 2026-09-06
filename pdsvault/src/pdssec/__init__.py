# SPDX-License-Identifier: MIT
"""pdsvault - offline, hardware-rooted, privacy-preserving Aadhaar
face-verification for PDS ration shops.

Reference implementation + test rig for the threat model documented in
docs/.  See docs/architecture.md for the full design.
"""

from . import crypto, identity, tpm, timekeeper, store, ledger, audit
from . import auth, entitlement, matcher, pad, sync, device
from .device import Device, DeviceConfig, TamperEvent, BootIntegrityError

__version__ = "0.1.0"