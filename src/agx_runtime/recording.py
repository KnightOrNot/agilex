"""A sole episode committer; bounded ingestion and independent finish deadlines."""

import os
import queue
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from agilex_contract import EpisodeBoundary, from_wire, to_wire

from . import raw
from .safety import sample_key, sample_ref


class Episode:
    def __init__(self, root, config, descriptors, policies, clients, metadata=None):
        self.id = uuid.uuid4().hex
        self.path = Path(root) / (self.id + ".partial")
        self.config, self.clients = config, clients
        self.start_ns = time.monotonic_ns()
        self.end_ns = None
        self.descriptors = {d.device_id: d for d in descriptors}
        self.policies = {p.key: p for p in policies}
        self.metadata = metadata or {}
        self.received = {p.key: {} for p in policies}
        self.selected = {p.key: set() for p in policies}
        self.written = {p.key: set() for p in policies}
        self.boundaries = {}
        self.last_kept = {}
        self.last_selection_ns = -1
        self.discard_requested = False
        self.warnings = {}
        self._quarantined = set()
        self.selection_count = 0
        self._drain_deadline = None
        self.error = None
        self.phase = "STARTING"
        self.started = False
        self.done = False
        self._lock = threading.Lock()
        self._terminal_lock = threading.Lock()
        self._queue = queue.Queue(config.queue_size)
        self._end = threading.Event()
        self._writer_ready = threading.Event()
        self._writer_done = threading.Event()
        self._prepared = threading.Event()
        self._writer = threading.Thread(target=self._write, daemon=True)
        self._coordinator = threading.Thread(target=self._coordinate, daemon=True)
        self._writer.start()
        self._coordinator.start()
        threading.Thread(target=self._watch_deadline, daemon=True).start()

    def _watch_deadline(self):
        # This worker performs no I/O and never waits on the disk/coordinator.
        self._end.wait()
        while not self.done:
            deadline = self._drain_deadline
            if deadline is None:
                deadline = self.end_ns / 1e9 + self.config.boundary_timeout_s
                reason = "boundary confirmation timed out"
            else:
                reason = (
                    "drain deadline exceeded (missing samples or unfinished writes)"
                )
            if time.monotonic() >= deadline:
                self.fail(reason)
                return
            time.sleep(min(0.002, max(0, deadline - time.monotonic())))

    def fail(self, reason):
        # Never waits for disk, a management request, or a writer's exit.
        with self._terminal_lock:
            if self.done:
                return
            self.error = self.error or str(reason)
            self.phase, self.done = "FAILED", True
        self._end.set()

    def _complete(self, deadline):
        # No filesystem operation is allowed under the terminal lock. Check
        # failure after reading the clock, so a concurrent fault always wins
        # until this short, atomic success transition.
        expired = time.monotonic() >= deadline
        with self._terminal_lock:
            if self.done or expired:
                return False
            self.phase, self.done = "COMPLETE", True
            return True

    def _put(self, kind, value):
        if self.done:
            return False
        try:
            self._queue.put_nowait((kind, value))
            return True
        except queue.Full:
            self.fail("recording queue full")
            return False

    def offer(self, sample):
        if self.done:
            return
        h, key = sample.header, sample_key(sample)
        if (
            key not in self.policies
            or key in self._quarantined
            or h.t_sample_ns is None
            or h.t_sample_ns < self.start_ns
            or (self.end_ns is not None and h.t_sample_ns > self.end_ns)
        ):
            return
        with self._lock:
            received = self.received[key]
            if (
                received
                and h.stream_epoch != next(iter(received.values())).stream_epoch
            ):
                if self.policies[key].role == "optional":
                    self._quarantined.add(key)
                    self.warnings[key] = (
                        "stream epoch changed; excluded for this episode"
                    )
                else:
                    self.fail(f"{key}: stream epoch changed")
                return
            if h.seq in received:
                return
            received[h.seq] = h
        if not h.valid or h.freshness == "stale":
            if self.policies[key].role != "optional":
                self.fail(f"{key}: invalid recording sample")
            return
        if self.config.mode == "full":
            if h.stream in ("rgb", "depth"):
                previous = self.last_kept.get(key)
                if (
                    previous is not None
                    and h.t_sample_ns - previous < 1e9 / self.config.capture_fps_max
                ):
                    return
                self.last_kept[key] = h.t_sample_ns
            self._select(sample)

    def _select(self, sample):
        key, seq = sample_key(sample), sample.header.seq
        with self._lock:
            if seq in self.selected[key]:
                return
            self.selected[key].add(seq)
        self._put("sample", sample)

    def selection(self, target_ns, samples):
        if (
            self.done
            or target_ns < self.start_ns
            or (self.end_ns is not None and target_ns > self.end_ns)
        ):
            return
        refs = []
        keys = set()
        if target_ns <= self.last_selection_ns:
            self.fail("selection target time must increase")
            return
        self.last_selection_ns = target_ns
        for sample in samples:
            key = sample_key(sample)
            reason = None
            if (
                key not in self.policies
                or key in self._quarantined
                or sample.header.seq not in self.received[key]
                or self.received[key][sample.header.seq].stream_epoch
                != sample.header.stream_epoch
            ):
                reason = "selection references a sample outside the episode"
            elif not sample.header.valid or sample.header.freshness == "stale":
                reason = "invalid selection sample"
            elif (
                abs(sample.header.t_sample_ns - target_ns)
                > self.config.max_skew_ms * 1e6
            ):
                reason = "selection sample skew exceeds limit"
            if reason:
                if key in self.policies and self.policies[key].role == "optional":
                    self.warnings[key] = reason
                    continue
                self.fail(reason)
                return
            if key in keys:
                self.fail("duplicate stream in selection")
                return
            keys.add(key)
            self._select(sample)
            refs.append(sample_ref(sample))
        if any(
            p.role != "optional" and key not in keys for key, p in self.policies.items()
        ):
            self.fail("selection is missing a required stream")
            return
        if self._put("selection", {"target_mono_ns": target_ns, "samples": refs}):
            self.selection_count += 1

    def command(self, command, observations):
        if command.issued_mono_ns < self.start_ns or (
            self.end_ns is not None and command.issued_mono_ns > self.end_ns
        ):
            return
        self._put("command", (command, tuple(observations)))

    def finish(self, end_ns):
        if self.done or self.end_ns is not None:
            return
        if (
            type(end_ns) is not int
            or not self.start_ns <= end_ns <= time.monotonic_ns()
        ):
            raise ValueError("invalid episode end")
        self.end_ns = end_ns
        self.phase = "BOUNDARY"
        self._end.set()

    def discard(self):
        self.discard_requested = True
        self.finish(time.monotonic_ns())

    def stats(self):
        with self._lock:
            result = {}
            for key, policy in self.policies.items():
                headers = list(self.received[key].values())
                boundary = self.boundaries.get(key)
                count = boundary.produced_count if boundary else None
                written = len(self.written[key])
                selected = len(self.selected[key])
                gaps = []
                if boundary and boundary.first_seq is not None:
                    cursor = boundary.first_seq
                    for seq in sorted(self.received[key]):
                        if seq > cursor:
                            gaps.append([cursor, seq - 1])
                        cursor = seq + 1
                    if cursor <= boundary.last_seq:
                        gaps.append([cursor, boundary.last_seq])
                result[key] = {
                    "episode_id": self.id,
                    "device_id": policy.device_id,
                    "stream": policy.stream,
                    "required": policy.role != "optional",
                    "stream_epoch": boundary.stream_epoch
                    if boundary
                    else (headers[0].stream_epoch if headers else None),
                    "first_seq": boundary.first_seq if boundary else None,
                    "last_seq": boundary.last_seq if boundary else None,
                    "produced": count,
                    "received": len(headers),
                    "written": written,
                    "intentional_skipped": len(headers) - selected,
                    "transport_lost": None
                    if count is None
                    else max(0, count - len(headers)),
                    "write_failed": max(0, selected - written) if self.error else 0,
                    "transport_gap_ranges": gaps,
                }
            return result

    def _manifest(self):
        return {
            "raw_schema_version": 3,
            "episode_id": self.id,
            "start_mono_ns": self.start_ns,
            "end_mono_ns": self.end_ns,
            "record": asdict(self.config),
            "devices": [to_wire(d) for d in self.descriptors.values()],
            "policies": [asdict(p) for p in self.policies.values()],
            "streams": self.stats(),
            "metadata": self.metadata,
            "warnings": dict(self.warnings),
        }

    def _write(self):
        try:
            self.path.mkdir(parents=True, exist_ok=False)
            raw.atomic_json(self.path / "manifest.json", self._manifest())
            self._writer_ready.set()
            while not self.done:
                try:
                    kind, value = self._queue.get(timeout=0.02)
                except queue.Empty:
                    continue
                if kind == "sample":
                    raw.write_sample(self.path, value)
                    with self._lock:
                        self.written[sample_key(value)].add(value.header.seq)
                elif kind == "selection":
                    raw.append_json(self.path / "selections.jsonl", value)
                elif kind == "command":
                    command, observations = value
                    raw.append_json(
                        self.path / "commands.jsonl",
                        {
                            "command": to_wire(command),
                            "observations": [to_wire(s) for s in observations],
                            "observation_refs": [sample_ref(s) for s in observations],
                        },
                    )
                elif kind == "finish":
                    raw.atomic_json(self.path / "manifest.json", self._manifest())
                    for file in self.path.rglob("*.jsonl"):
                        with file.open("rb") as stream:
                            os.fsync(stream.fileno())
                    self._prepared.set()
                    return
        except Exception as exc:
            self.fail(f"write failed: {exc}")
        finally:
            self._writer_done.set()

    def _boundaries(self, method, deadline):
        results = queue.Queue()
        arguments = {
            "episode_id": self.id,
            "start_mono_ns"
            if method == "boundary_begin"
            else "end_mono_ns": self.start_ns
            if method == "boundary_begin"
            else self.end_ns,
        }

        def request(device_id, client):
            try:
                results.put((device_id, client.request(method, **arguments), None))
            except Exception as exc:
                results.put((device_id, None, str(exc)))

        for device_id, client in self.clients.items():
            threading.Thread(
                target=request, args=(device_id, client), daemon=True
            ).start()
        pending = set(self.clients)
        while pending and not self.done:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                device_id, result, error = results.get(timeout=min(0.01, remaining))
            except queue.Empty:
                continue
            pending.remove(device_id)
            if error:
                if any(
                    p.device_id == device_id and p.role != "optional"
                    for p in self.policies.values()
                ):
                    self.fail(f"boundary error: {error}")
                    return False
                continue
            if method == "boundary_end":
                if result.get("metadata"):
                    self.metadata.setdefault("hal_metadata", {})[device_id] = result[
                        "metadata"
                    ]
                for wire in result["boundaries"]:
                    boundary = from_wire(wire)
                    key = f"{boundary.device_id}/{boundary.stream}"
                    if (
                        not isinstance(boundary, EpisodeBoundary)
                        or boundary.episode_id != self.id
                        or boundary.device_id != device_id
                    ):
                        raise ValueError("boundary identity mismatch")
                    if key in self.policies:
                        with self._lock:
                            headers = self.received[key]
                            if headers and any(
                                h.stream_epoch != boundary.stream_epoch
                                or boundary.first_seq is None
                                or not boundary.first_seq <= seq <= boundary.last_seq
                                for seq, h in headers.items()
                            ):
                                if self.policies[key].role == "optional":
                                    self.warnings[key] = (
                                        "boundary disagrees with received samples"
                                    )
                                    continue
                                raise ValueError(
                                    "producer boundary disagrees with received samples"
                                )
                            self.boundaries[key] = boundary
        if any(
            p.device_id in pending and p.role != "optional"
            for p in self.policies.values()
        ):
            self.fail("boundary confirmation timed out")
            return False
        if method == "boundary_end" and any(
            key not in self.boundaries and p.role != "optional"
            for key, p in self.policies.items()
        ):
            self.fail("missing required boundary")
            return False
        return not self.done

    def _coordinate(self):
        try:
            if not self._boundaries(
                "boundary_begin", time.monotonic() + self.config.boundary_timeout_s
            ):
                return
            if not self._writer_ready.wait(self.config.drain_timeout_s):
                self.fail("writer preparation timed out")
                return
            if self.done:
                return
            self.started = True
            self.phase = "RECORDING" if self.end_ns is None else "BOUNDARY"
            self._end.wait()
            if self.done:
                return
            deadline = self.end_ns / 1e9 + self.config.boundary_timeout_s
            if not self._boundaries("boundary_end", deadline):
                return
            if self.discard_requested:
                with self._terminal_lock:
                    if self.done:
                        return
                    self.phase, self.done = "DISCARDED", True
                raw.atomic_json(
                    self.path / "discarded.json",
                    {
                        "episode_id": self.id,
                        "end_mono_ns": self.end_ns,
                        "reason": "discarded by operator",
                        "streams": self.stats(),
                    },
                )
                return
            deadline = time.monotonic() + self.config.drain_timeout_s
            self._drain_deadline = deadline
            self.phase = "DRAINING"
            while not self.done:
                stats = self.stats()
                missing = any(
                    s["required"]
                    and (s["produced"] is None or s["received"] != s["produced"])
                    for s in stats.values()
                )
                if not missing:
                    break
                if time.monotonic() >= deadline:
                    self.fail("missing required samples at drain deadline")
                    return
                time.sleep(0.002)
            if self.done:
                return
            if any(s["required"] and not s["produced"] for s in self.stats().values()):
                self.fail("empty required stream")
                return
            if self.config.mode == "sampled" and not self.selection_count:
                self.fail("recording too short: no valid sampled selection")
                return
            if not self._put("finish", None):
                return
            while not self._prepared.is_set() and not self.done:
                if time.monotonic() >= deadline:
                    self.fail("drain deadline exceeded while writing")
                    return
                self._prepared.wait(0.002)
            if self.done:
                return
            complete = {
                "raw_schema_version": 3,
                "episode_id": self.id,
                "files": raw.inventory(self.path),
            }
            if self.done or time.monotonic() >= deadline:
                self.fail("drain deadline exceeded during integrity check")
                return
            raw.atomic_json(self.path / "complete.json", complete)
            if self.done or time.monotonic() >= deadline:
                (self.path / "complete.json").unlink(missing_ok=True)
                self.fail("drain deadline exceeded before publication")
                return
            destination = self.path.with_suffix("")
            os.rename(self.path, destination)
            self.path = destination
            if not self._complete(deadline):
                # A late filesystem operation cannot reverse a terminal failure.
                (destination / "complete.json").unlink(missing_ok=True)
                os.rename(
                    destination, destination.with_name(destination.name + ".partial")
                )
                self.path = destination.with_name(destination.name + ".partial")
                self.fail("drain deadline exceeded during publication")
                return
        except Exception as exc:
            self.fail(f"recording failed: {exc}")
        finally:
            if self.error:
                # Diagnostic I/O never holds a lock needed by the runtime.
                try:
                    if self.path.is_dir():
                        raw.atomic_json(
                            self.path / "failure.json",
                            {
                                "error": self.error,
                                "episode_id": self.id,
                                "streams": self.stats(),
                            },
                        )
                except OSError:
                    pass


class Recorder:
    def __init__(self, root, config):
        self.root, self.config = Path(root), config
        self.episodes = []

    def start(self, descriptors, policies, clients, metadata=None):
        if self.episodes and not self.episodes[-1].done:
            raise ValueError("previous episode is still active or finishing")
        episode = Episode(
            self.root, self.config, descriptors, policies, clients, metadata
        )
        self.episodes.append(episode)
        return episode

    def close(self):
        for episode in self.episodes:
            if not episode.done:
                episode.fail("session stopped before episode was saved")
