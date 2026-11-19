"""Descriptor-driven checks; no hardware construction or implicit motion policy."""

import math

from agilex_contract import JointState


class SafetyFault(RuntimeError):
    pass


def sample_key(sample):
    return f"{sample.header.device_id}/{sample.header.stream}"


def sample_ref(sample):
    h = sample.header
    return {
        "device_id": h.device_id,
        "stream": h.stream,
        "stream_epoch": h.stream_epoch,
        "seq": h.seq,
    }


def fresh(sample, spec, now_ns):
    h = sample.header
    if not h.valid or h.freshness == "stale" or h.origin == "unknown":
        raise SafetyFault("invalid or stale feedback")
    if (
        h.clock_domain != "host_monotonic"
        or h.t_sample_ns is None
        or h.clock_uncertainty_ns is None
    ):
        raise SafetyFault("sample clock cannot be compared to runtime")
    if (
        not 0 <= now_ns - h.t_sample_ns
        or now_ns - h.t_sample_ns + h.clock_uncertainty_ns >= spec.stale_after_ns
    ):
        raise SafetyFault("stale or future sample time")
    if not 0 <= now_ns - h.t_host_rx_mono_ns < spec.stale_after_ns:
        raise SafetyFault("stale or future host receive time")


class StreamMonitor:
    def __init__(self, descriptors, policies):
        self.specs = {
            f"{d.device_id}/{s.name}": s for d in descriptors for s in d.streams
        }
        self.policies = {p.key: p for p in policies}
        if set(self.policies) - set(self.specs):
            raise ValueError("policy references an unknown stream")
        self.latest = {}
        self.errors = {}

    def update(self, sample):
        key = sample_key(sample)
        if key not in self.policies:
            return
        previous = self.latest.get(key)
        error = None
        if previous is not None:
            old, new = previous.header, sample.header
            if new.stream_epoch != old.stream_epoch:
                error = "stream epoch changed"
            elif new.seq < old.seq:
                error = "stream sequence moved backwards"
            elif new.seq == old.seq:
                if (
                    new.t_sample_ns != old.t_sample_ns
                    or new.t_host_rx_mono_ns != old.t_host_rx_mono_ns
                    or sample.payload != previous.payload
                ):
                    error = "cached sample changed its time or payload"
                else:
                    self.latest[key] = sample
                    return
            elif new.t_host_rx_mono_ns < old.t_host_rx_mono_ns:
                error = "stream time moved backwards"
        if error:
            self.errors[key] = error
            if self.policies[key].role != "optional":
                raise SafetyFault(f"{key}: {error}")
            return
        self.latest[key] = sample

    def check(self, phase, now_ns):
        warnings = []
        for key, policy in self.policies.items():
            if phase not in policy.monitor_when:
                continue
            try:
                if key in self.errors:
                    raise SafetyFault(self.errors[key])
                if key not in self.latest:
                    raise SafetyFault("missing stream")
                fresh(self.latest[key], self.specs[key], now_ns)
            except SafetyFault as exc:
                message = f"{key}: {exc}"
                if policy.role != "optional":
                    raise SafetyFault(message) from exc
                warnings.append(message)
        return warnings

    def quality(self, phase, now_ns, max_skew_ms, reference=None):
        warnings = self.check(phase, now_ns)
        reference_sample = self.latest.get(reference) if reference else None
        for key, policy in self.policies.items():
            if phase not in policy.monitor_when or self.specs[key].kind not in (
                "rgb",
                "depth",
            ):
                continue
            sample = self.latest.get(key)
            if sample is None:
                continue
            try:
                fresh(sample, self.specs[key], now_ns)
            except SafetyFault:
                continue  # Optional bad samples were already reported by check().
            reference_sample = reference_sample or sample
            skew = abs(sample.header.t_sample_ns - reference_sample.header.t_sample_ns)
            if skew > max_skew_ms * 1e6:
                message = f"{key}: sample skew exceeds limit"
                if policy.role != "optional":
                    raise SafetyFault(message)
                warnings.append(message)
        return warnings


class JointMapping:
    def __init__(self, leader, follower, routes=None):
        spec = next((s for s in leader.streams if s.name == "joints"), None)
        if spec is None or spec.unit != "rad" or not follower.joint_names:
            raise ValueError("mapping requires compatible radian joint streams")
        self.source_names = spec.channels
        self.target_names = follower.joint_names
        if routes is None or not routes:
            routes = {name: (name, 1.0) for name in self.target_names}
        if set(routes) != set(self.target_names) or len(self.source_names) != len(
            self.target_names
        ):
            raise ValueError(
                "incompatible joint structures require explicit retargeting"
            )
        self.routes = []
        used = set()
        for target in self.target_names:
            source, scale = routes[target]
            if (
                source not in self.source_names
                or source in used
                or type(scale) not in (int, float)
                or not math.isfinite(scale)
                or scale == 0
            ):
                raise ValueError("invalid joint name/scale mapping")
            used.add(source)
            self.routes.append((self.source_names.index(source), scale))

    def target(self, sample):
        if (
            not isinstance(sample.payload, JointState)
            or sample.payload.names != self.source_names
        ):
            raise SafetyFault("leader channel order disagrees with mapping")
        return tuple(sample.payload.positions[i] * scale for i, scale in self.routes)


def checked_positions(descriptor, feedback, target, now_ns, *, max_step=None):
    spec = next((s for s in descriptor.streams if s.name == "joints"), None)
    if spec is None or sample_key(feedback) != f"{descriptor.device_id}/joints":
        raise SafetyFault("missing joint feedback")
    fresh(feedback, spec, now_ns)
    if (
        not isinstance(feedback.payload, JointState)
        or feedback.payload.names != descriptor.joint_names
    ):
        raise SafetyFault("invalid feedback channels")
    if len(target) != len(descriptor.joint_names) or any(
        type(v) not in (int, float) or not math.isfinite(v) for v in target
    ):
        raise SafetyFault("invalid target dimensions or values")
    if any(
        not low <= value <= high
        for value, (low, high) in zip(target, descriptor.joint_limits, strict=True)
    ):
        raise SafetyFault("target outside device limits")
    current = feedback.payload.positions
    if feedback.header.origin == "command_filled" or any(
        not low <= value <= high
        for value, (low, high) in zip(current, descriptor.joint_limits, strict=True)
    ):
        raise SafetyFault("feedback cannot authorize movement")
    delta = max(abs(a - b) for a, b in zip(target, current, strict=True))
    if max_step is not None and delta > max_step:
        return tuple(
            b + (a - b) * max_step / delta for a, b in zip(target, current, strict=True)
        )
    return tuple(target)
