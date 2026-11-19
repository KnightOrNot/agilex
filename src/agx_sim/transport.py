"""Compatibility import for the P1 client; implementation is hardware independent."""

from agx_transport import (  # noqa: F401
    MAX_METADATA_BYTES,
    HalClient,
    decode_event,
    encode_event,
    endpoints,
    pack,
    unpack,
)
