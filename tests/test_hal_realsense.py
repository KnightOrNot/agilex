"""The camera HAL preserves native bytes, independent clocks and calibration."""

import importlib
import importlib.util
from types import SimpleNamespace

import numpy as np
import pytest


class Stream:
    def __init__(self, **kwargs):
        self.started = self.closed = False
        self.metadata = {
            "device": {"serial_number": "test"},
            "fps": 30,
            "width": 2,
            "height": 1,
            "intrinsics": {"fx": 1.0},
            "depth": {
                "fps": 30,
                "width": 2,
                "height": 1,
                "depth_units_m": 0.001,
                "intrinsics": {"fx": 2.0},
            },
        }
        self.frames = []

    def start(self):
        self.started = True
        return self

    def read(self, timeout_s):
        return self.frames.pop(0) if self.frames else None

    def close(self):
        self.closed = True


def wrapper(stream):
    assert importlib.util.find_spec("agx_hal_realsense"), "RealSense HAL is missing"
    return importlib.import_module("agx_hal_realsense.device").RealSenseDevice(
        {
            "device_id": "front",
            "serial": "test",
            "width": 2,
            "height": 1,
            "depth_width": 2,
            "depth_height": 1,
        },
        stream_factory=lambda **kwargs: stream,
        probe=lambda settings: {"serial_number": "test"},
    )


def frame(kind, seq=10, domain="global_time"):
    image = (
        np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8)
        if kind == "color"
        else np.array([[0, 65535]], dtype=np.uint16)
    )
    return SimpleNamespace(
        stream=kind,
        image=image,
        timestamp_ns=1_000_000_000 + (0 if kind == "color" else 5000),
        received_time_ns=1_001_000_000,
        sdk_timestamp_ms=123.0,
        sdk_timestamp_domain=domain,
        frame_number=seq,
        clock_offset_ns=-122_000_000_000,
        clock_uncertainty_ns=2000,
    )


def test_discovery_does_not_start_camera_and_prepare_exposes_final_metadata():
    stream = Stream()
    hal = wrapper(stream)
    hal.discover()
    assert not stream.started
    hal.prepare()
    assert stream.started and hal.metadata["camera"]["depth"]["depth_units_m"] == 0.001
    assert "configure_and_start_streams" in hal.descriptor.prepare_effects
    hal.close()
    hal.close()
    assert stream.closed


def test_native_color_and_depth_keep_separate_times_original_bytes_and_scale():
    stream = Stream()
    hal = wrapper(stream)
    hal.prepare()
    stream.frames = [frame("color"), frame("depth")]
    color = hal.samples(1_002_000_000)[0]
    depth = hal.samples(1_003_000_000)[0]
    assert color.payload.data == bytes([1, 2, 3, 4, 5, 6])
    assert depth.payload.data == b"\x00\x00\xff\xff"
    assert depth.payload.depth_scale_m == 0.001
    assert color.header.t_sample_ns == 1_000_000_000
    assert depth.header.t_sample_ns == 1_000_005_000
    assert depth.header.clock_uncertainty_ns == 2000
    assert depth.payload.info.frame_number == 10
    assert depth.payload.info.clock_offset_ns == -122_000_000_000
    assert depth.payload.info.calibration_id in hal.metadata["calibrations"]
    assert hal.metadata["frames"]["depth"]["sdk_timestamp_domain"] == "global_time"
    hal.close()


def test_duplicate_frame_is_not_republished_as_new_and_counter_reset_fails():
    stream = Stream()
    hal = wrapper(stream)
    hal.prepare()
    stream.frames = [frame("color"), frame("color"), frame("color", 9)]
    assert hal.samples(1_002_000_000)
    assert hal.samples(1_003_000_000) == []
    with pytest.raises(ValueError, match="frame"):
        hal.samples(1_004_000_000)
    hal.close()


def test_unknown_timestamp_domain_is_rejected():
    stream = Stream()
    hal = wrapper(stream)
    hal.prepare()
    stream.frames = [frame("color", domain="hardware_clock")]
    with pytest.raises(ValueError, match="clock"):
        hal.samples(1_002_000_000)
    hal.close()


def test_new_prepare_after_close_starts_a_new_epoch_and_accepts_reset_frame_counter():
    stream = Stream()
    hal = wrapper(stream)
    hal.prepare()
    stream.frames = [frame("color")]
    first = hal.samples(1_002_000_000)[0]
    hal.close()
    hal.prepare()
    stream.frames = [frame("color")]
    second = hal.samples(1_002_000_000)
    assert second and second[0].header.stream_epoch != first.header.stream_epoch
    assert second[0].header.seq == 0
    hal.close()
