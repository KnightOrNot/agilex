"""Publish the camera library's original frames and clock/calibration evidence."""

import hashlib
import json
from dataclasses import replace

from agilex_contract import (
    CameraFrameInfo,
    DepthFrame,
    DeviceDescriptor,
    ImageFrame,
    StreamSpec,
)

from agx_hal.device import HardwareDevice


def probe_camera(settings):
    from camera_realsense.device import device_info, select_device

    return device_info(select_device(settings["serial"]))


def create_stream(**settings):
    from camera_realsense.stream import ColorStream

    return ColorStream(**settings)


class RealSenseDevice(HardwareDevice):
    def __init__(self, settings, *, stream_factory=None, probe=None):
        self.settings = dict(settings)
        self._factory = stream_factory or create_stream
        self._probe = probe or probe_camera
        self._stream = None
        self._discovered = False
        self._numbers = {}
        self._domains = {}
        self._calibration = ""
        fps = settings.get("fps", 30)
        depthfps = settings.get("depth_fps", fps)
        descriptor = DeviceDescriptor(
            settings["device_id"],
            "realsense",
            settings["serial"],
            "camera-realsense",
            (
                StreamSpec("rgb", "rgb", (), "rgb8", fps, round(3e9 / fps)),
                StreamSpec(
                    "depth", "depth", (), "z16_le", depthfps, round(3e9 / depthfps)
                ),
            ),
            prepare_effects=("configure_and_start_streams",),
            exit_policy="stop_and_restore_camera",
            disconnect_behavior="unverified",
        )
        super().__init__(descriptor, 2 * max(fps, depthfps))

    def discover(self):
        if not self._discovered:
            self.metadata["probe"] = self._probe(self.settings)
            self._discovered = True

    def prepare(self):
        if self.prepared:
            return
        self.discover()
        settings = {
            key: self.settings[key]
            for key in (
                "serial",
                "width",
                "height",
                "fps",
                "warmup_frames",
                "depth_width",
                "depth_height",
                "depth_fps",
                "mode",
            )
            if key in self.settings
        }
        stream = self._factory(**settings, depth_enabled=True)
        try:
            stream.start()
        except BaseException:
            stream.close()
            raise
        self._stream = stream
        camera = dict(stream.metadata)
        self._calibration = hashlib.sha256(
            json.dumps(camera, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
        self.metadata.update(
            camera=camera, calibrations={self._calibration: camera}, frames={}
        )
        fps = camera["fps"]
        depthfps = camera["depth"]["fps"]
        specs = (
            replace(
                self.descriptor.streams[0],
                nominal_hz=fps,
                stale_after_ns=round(3e9 / fps),
            ),
            replace(
                self.descriptor.streams[1],
                nominal_hz=depthfps,
                stale_after_ns=round(3e9 / depthfps),
            ),
        )
        self.descriptor = replace(self.descriptor, streams=specs)
        self.publisher.descriptor = self.descriptor
        self.hz = 2 * max(fps, depthfps)
        self.begin_streams()
        self._numbers.clear()
        self._domains.clear()
        self.prepared = True

    def samples(self, now_ns):
        if not self.prepared:
            return []
        frame = self._stream.read(timeout_s=0.005)
        if frame is None:
            return []
        name = "rgb" if frame.stream == "color" else "depth"
        if frame.sdk_timestamp_domain not in ("global_time", "system_time"):
            raise ValueError("unmapped camera clock domain")
        if name in self._domains and self._domains[name] != frame.sdk_timestamp_domain:
            raise ValueError("camera clock domain changed")
        previous = self._numbers.get(name)
        if previous is not None:
            if frame.frame_number == previous:
                return []
            if frame.frame_number < previous:
                raise ValueError("camera frame counter reset")
        self._numbers[name] = frame.frame_number
        self._domains[name] = frame.sdk_timestamp_domain
        info = CameraFrameInfo(
            frame.sdk_timestamp_ms,
            frame.sdk_timestamp_domain,
            frame.frame_number,
            frame.clock_offset_ns,
            self._calibration,
        )
        if name == "rgb":
            if frame.image.dtype.name != "uint8" or frame.image.shape[-1] != 3:
                raise ValueError("invalid RGB image layout")
            payload = ImageFrame(
                frame.image.shape[1],
                frame.image.shape[0],
                frame.image.tobytes(),
                info=info,
            )
        else:
            if frame.image.dtype.name != "uint16" or frame.image.ndim != 2:
                raise ValueError("invalid native depth layout")
            payload = DepthFrame(
                frame.image.shape[1],
                frame.image.shape[0],
                frame.image.astype("<u2", copy=False).tobytes(),
                self.metadata["camera"]["depth"]["depth_units_m"],
                info=info,
            )
        self.metadata["frames"][name] = {
            "sdk_timestamp_domain": frame.sdk_timestamp_domain,
            "frame_number": frame.frame_number,
        }
        return [
            self.publisher.sample(
                name,
                payload,
                t_sample_ns=frame.timestamp_ns,
                t_host_rx_mono_ns=frame.received_time_ns,
                t_publish_mono_ns=max(now_ns, frame.received_time_ns),
                source_key=frame.frame_number,
                clock_uncertainty_ns=frame.clock_uncertainty_ns,
            )
        ]

    def close(self):
        stream, self._stream = self._stream, None
        self.prepared = False
        if stream is not None:
            stream.close()

    def release(self):
        self.close()
