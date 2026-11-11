"""Exercise the real service loop with a deterministic clock and socket queues."""

from collections import deque
from statistics import median

import zmq
from agilex_contract import Ack, Command, Sample, to_wire

from agx_sim import server
from agx_sim.control import ControlGate
from agx_sim.devices import SimDevice
from agx_sim.transport import pack


def loop_fixture(monkeypatch, kind, hz, turns):
    now = [1_000_000_000]
    incoming = deque()
    events = []

    class Socket:
        def recv_multipart(self, flags):
            if not incoming:
                raise zmq.Again()
            return [incoming.popleft()]

        def poll(self, timeout, flags):
            return zmq.POLLIN if incoming else 0

    service = server.HalServer.__new__(server.HalServer)
    service.device = SimDevice(kind, "test-device", hz=hz)
    service.gate = ControlGate(service.device)
    service.sockets = {"rpc": object(), "commands": Socket()}
    service.stopping = False
    service.protocol_errors = 0
    service._publish = events.append
    service.close = lambda: None
    lease = service.gate.acquire("session", now[0])
    service.gate.prepare("session", lease, now[0])

    class Poller:
        calls = 0

        def register(self, *args):
            pass

        def poll(self, timeout):
            self.calls += 1
            now[0] += max(1000, timeout * 1_000_000)
            if self.calls >= turns:
                service.stopping = True
            return []

    monkeypatch.setattr(server.zmq, "Poller", Poller)
    monkeypatch.setattr(server.time, "monotonic_ns", lambda: now[0])
    return service, incoming, events, lease, now[0]


def test_backlog_submits_only_latest_target_and_still_publishes(monkeypatch):
    service, incoming, events, lease, now = loop_fixture(
        monkeypatch, "follower", 1000, 6
    )
    service.gate.authorize("session", lease, now)
    service.gate.begin_alignment("session", lease, now)

    def command(seq):
        return Command(
            "session",
            lease,
            seq,
            now,
            now + 1_000_000_000,
            service.device.descriptor.joint_names,
            (seq / 1000,) * 6,
        )

    service.gate.alignment_step(command(0), now)
    service.gate.activate("session", lease, now)
    incoming.extend(pack(to_wire(command(seq))) for seq in range(1, 101))
    service.run()
    submitted = [
        event.cmd_seq
        for event in events
        if isinstance(event, Ack) and event.status == "submitted"
    ]
    assert submitted == [100]
    final = next(
        i for i, e in enumerate(events) if isinstance(e, Ack) and e.cmd_seq == 100
    )
    assert any(isinstance(e, Sample) for e in events[:final])


def test_sampling_deadline_is_respected_at_declared_high_rate(monkeypatch):
    service, _, events, _, _ = loop_fixture(monkeypatch, "camera", 1000, 30)
    service.run()
    timestamps = [
        event.header.t_sample_ns
        for event in events
        if isinstance(event, Sample) and event.header.stream == "rgb"
    ]
    gaps = [b - a for a, b in zip(timestamps, timestamps[1:])]
    assert len(gaps) >= 20
    assert median(gaps) <= 1_000_000
