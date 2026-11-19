"""Wrap the checked SDK driver without invoking legacy start/enable together."""

import math
import time

from agilex_contract import DeviceDescriptor, JointState, StreamSpec

from agx_hal.device import HardwareDevice, WallClockBridge

# Match SDK nominal limits and its existing five-degree calibration margin.
_NOMINAL = (
    (-2.617994, 2.617994),
    (0.0, 3.141593),
    (-2.967060, 0.0),
    (-1.553344, 1.553344),
    (-1.553344, 1.553344),
    (-3.141593, 3.141593),
)


class PiperXDevice(HardwareDevice):
    def __init__(
        self,
        settings,
        *,
        driver_factory=None,
        clock_ns=time.monotonic_ns,
        wall_ns=time.time_ns,
    ):
        self.settings = dict(settings)
        names = tuple(f"joint_{n}" for n in range(1, 7))
        hz = settings.get("hz", 50.0)
        self.feedback_timeout = settings.get("feedback_timeout_s", 0.5)
        stale = round(self.feedback_timeout * 1e9)
        self.width = settings.get("gripper_max_width_m", 0.1)
        margin = math.radians(5.0)
        descriptor = DeviceDescriptor(
            settings["device_id"],
            "piperx",
            settings.get("channel", "can0"),
            "agilex-sdk-python",
            (
                StreamSpec("joints", "joint", names, "rad", hz, stale),
                StreamSpec("gripper", "joint", ("gripper",), "m", hz, stale),
            ),
            names,
            tuple((a - margin, b + margin) for a, b in _NOMINAL),
            (0.0, self.width),
            (),
            settings.get("exit_policy", "piperx_return_zero"),
            "unverified",
        )
        super().__init__(descriptor, hz)
        self._factory = driver_factory
        self._driver = None
        self._clock = clock_ns
        self._bridge = WallClockBridge(clock_ns, wall_ns)
        self._last_measured_gripper = None
        self._last_command = None
        self._check_lease = None

    def bind_authority_check(self, check):
        self._check_lease = check

    def _check_write(self, generation, command=None):
        if self._check_lease is not None:
            self._check_lease()
        with self._authority_lock:
            if generation != self._generation or (
                command is not None and not self.authorized
            ):
                raise RuntimeError("motion authority revoked")
            if command is not None and self._clock() >= command.expires_mono_ns:
                raise RuntimeError("command expired before SDK write")

    def discover(self):
        if self._driver is not None:
            return
        factory = self._factory
        if factory is None:
            from agilex_sdk_python.driver import PiperXDriver

            factory = PiperXDriver
        driver = factory(
            channel=self.settings.get("channel", "can0"),
            interface=self.settings.get("interface", "socketcan"),
            firmware=self.settings.get("firmware", "default"),
            feedback_timeout=self.feedback_timeout,
            max_command_delta_rad=self.settings.get("max_command_step_rad", 1.0),
        )
        try:
            driver.connect()
        except BaseException:
            driver.close()
            raise
        self._driver = driver
        self.metadata = {
            "disconnect_behavior": "unverified",
            "channel": self.settings.get("channel", "can0"),
            "gripper_max_width_m": self.width,
            "feedback_timeout_s": self.feedback_timeout,
        }

    def prepare(self):
        if self.prepared:
            return
        self.discover()
        self.begin_streams()
        self.prepared = True

    def authorize(self):
        if not self.prepared:
            raise RuntimeError("prepare required")
        with self._authority_lock:
            generation = self._generation

        def permitted():
            self._check_write(generation)

        if self.settings.get("configure_motion_limits", True):
            permitted()
            confirmed = self._driver.maximize_joint_motion_limits(
                require_confirmation=True, before_send=permitted
            )
            self.metadata["motion_limits_confirmed"] = bool(confirmed)
        permitted()
        self._driver.enable(before_send=permitted)
        permitted()
        with self._authority_lock:
            self.authorized = generation == self._generation

    def authorize_cleanup(self):
        if not self.prepared:
            raise RuntimeError("prepare required")
        with self._authority_lock:
            generation = self._generation
        self._check_write(generation)
        self._bridge.observe()
        state = self._driver.require_motion_ready()
        stamp = self._bridge.map(state.feedback_timestamp)
        if self._clock() - stamp > round(self.feedback_timeout * 1e9):
            raise RuntimeError("cleanup feedback is stale")
        self._check_write(generation)
        with self._authority_lock:
            self.authorized = generation == self._generation

    def samples(self, now_ns):
        if not self.prepared:
            return []
        self._bridge.observe()
        state = self._driver.get_state()
        timestamp = getattr(state, "joint_feedback_timestamp", None)
        timestamp = state.feedback_timestamp if timestamp is None else timestamp
        sample_ns = self._bridge.map(timestamp)
        published = self._clock()
        self.positions = tuple(state.joint_positions_rad)
        valid = bool(
            state.communication_ok
            and not state.errors.any
            and state.arm_status == 0
            and (not self.authorized or all(state.enabled_joints))
        )
        joints = self.publisher.sample(
            "joints",
            JointState(self.descriptor.joint_names, self.positions, (0.0,) * 6),
            t_sample_ns=sample_ns,
            t_host_rx_mono_ns=sample_ns,
            t_publish_mono_ns=published,
            source_key=timestamp,
            valid=valid,
            clock_uncertainty_ns=self._bridge.uncertainty,
        )
        try:
            status = self._driver.get_gripper_status()
            timestamp = status.get("feedback_timestamp")
            stamp = self._bridge.map(timestamp)
            width = float(status["value"])
            valid = (
                math.isfinite(width)
                and 0 <= width <= self.width
                and not status.get("error", False)
            )
            gripper = self.publisher.sample(
                "gripper",
                JointState(("gripper",), (width,), (0.0,)),
                t_sample_ns=stamp,
                t_host_rx_mono_ns=stamp,
                t_publish_mono_ns=self._clock(),
                source_key=timestamp,
                valid=valid,
                clock_uncertainty_ns=self._bridge.uncertainty,
            )
            if valid:
                self._last_measured_gripper = gripper
        except Exception:
            # A lost optional gripper feedback never becomes a fresh command echo.
            previous = self._last_measured_gripper
            if previous is not None:
                gripper = self.publisher.sample(
                    "gripper",
                    previous.payload,
                    t_sample_ns=previous.header.t_sample_ns,
                    t_host_rx_mono_ns=previous.header.t_host_rx_mono_ns,
                    t_publish_mono_ns=self._clock(),
                    source_key=self.publisher._sources["gripper"],
                )
            else:
                command = self._last_command
                width = (
                    command.gripper_m
                    if command is not None and command.gripper_m is not None
                    else 0.0
                )
                gripper = self.publisher.sample(
                    "gripper",
                    JointState(("gripper",), (width,), (0.0,)),
                    t_sample_ns=None if command is None else command.issued_mono_ns,
                    t_host_rx_mono_ns=self._clock(),
                    t_publish_mono_ns=self._clock(),
                    source_key="unknown"
                    if command is None
                    else ("command", command.cmd_seq),
                    origin="unknown" if command is None else "command_filled",
                    valid=False,
                )
        return [joints, gripper]

    def apply(self, command):
        with self._authority_lock:
            generation = self._generation

        def permitted():
            self._check_write(generation, command)

        permitted()
        self._driver.begin_fast_response_mode(before_send=permitted)
        permitted()
        self._driver.command_joints(
            command.positions, fast_response=True, before_send=permitted
        )
        if command.gripper_m is not None:
            permitted()
            self._driver.command_gripper(
                command.gripper_m,
                self.settings.get("gripper_force_n", 1.0),
                before_send=permitted,
            )
        self._last_command = command

    def close(self):
        self.revoke("closed")
        driver, self._driver = self._driver, None
        self._last_measured_gripper = None
        self._last_command = None
        try:
            if driver is not None:
                driver.close()
        finally:
            self.prepared = False
