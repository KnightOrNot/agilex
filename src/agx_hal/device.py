"""Small device-side lifecycle and a conservative wall-to-monotonic bridge."""

import math
import threading
import time

from .streams import StreamPublisher


class HardwareDevice:
    def __init__(self, descriptor, hz):
        self.descriptor, self.hz = descriptor, hz
        self.publisher = StreamPublisher(descriptor)
        self.epoch = self.publisher.epoch
        self.prepared = False
        self.positions = (0.0,) * len(descriptor.joint_names)
        self.metadata = {}
        self.authorized = False
        self._generation = 0
        self._authority_lock = threading.RLock()
        self._stream_started = False

    def begin_episode(self, *args):
        if not self.prepared:
            raise ValueError("device is not prepared")
        return self.publisher.begin_episode(*args)

    def end_episode(self, *args):
        return self.publisher.end_episode(*args)

    def abort_episode(self, *args):
        return self.publisher.abort_episode(*args)

    def revoke(self, reason):
        with self._authority_lock:
            self.authorized = False
            self._generation += 1

    def begin_streams(self):
        if self._stream_started:
            previous = self.publisher
            self.publisher = StreamPublisher(self.descriptor)
            with previous._counter_lock:
                history = dict(previous._closed_episodes)
                if (
                    previous._episode is not None
                    and previous._episode["result"] is not None
                ):
                    history[previous._episode["id"]] = previous._episode
            self.publisher._closed_episodes = dict(list(history.items())[-16:])
            self.epoch = self.publisher.epoch
        self._stream_started = True


class WallClockBridge:
    def __init__(self, clock_ns=time.monotonic_ns, wall_ns=time.time_ns):
        self.clock_ns, self.wall_ns = clock_ns, wall_ns
        self.offset = None
        self.uncertainty = 0

    def observe(self):
        before = self.clock_ns()
        wall = self.wall_ns()
        after = self.clock_ns()
        if after < before or after - before > 5_000_000:
            raise RuntimeError("host clock sampling exceeded 5ms")
        offset = (before + after) // 2 - wall
        if self.offset is not None and abs(offset - self.offset) > 5_000_000:
            raise RuntimeError("wall clock stepped; feedback clock is invalid")
        self.offset = offset
        self.uncertainty = after - before

    def map(self, timestamp):
        if (
            type(timestamp) not in (int, float)
            or not math.isfinite(timestamp)
            or timestamp < 0
        ):
            raise ValueError("invalid SDK source timestamp")
        mapped = round(timestamp * 1e9) + self.offset
        if mapped < 0 or mapped > self.clock_ns() + self.uncertainty:
            raise ValueError("SDK source timestamp is in the future")
        return mapped
