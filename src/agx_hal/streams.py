"""Shared source identity and producer counters, independent of any driver."""

import threading
import uuid
from collections import deque
from dataclasses import replace
from functools import wraps

from agilex_contract import EpisodeBoundary, Sample, SampleHeader


def _locked(function):
    @wraps(function)
    def locked(self, *args, **kwargs):
        with self._counter_lock:
            return function(self, *args, **kwargs)

    return locked


class EpisodeCounters:
    def _init_counters(self):
        self._counter_lock = threading.RLock()
        self._history = {}
        self._episode = None
        self._closed_episodes = {}

    @_locked
    def track(self, sample):
        h = sample.header
        if h.t_sample_ns is None:
            return
        self._history.setdefault(h.stream, deque(maxlen=8192)).append(
            (h.t_sample_ns, h.seq)
        )
        if self._episode is not None and self._episode["result"] is None:
            if h.t_sample_ns >= self._episode["start"]:
                self._episode["first"].setdefault(h.stream, h.seq)

    @_locked
    def begin_episode(self, episode_id, start_ns, now_ns):
        if not isinstance(episode_id, str) or not episode_id or len(episode_id) > 128:
            raise ValueError("invalid episode id")
        if (
            type(start_ns) is not int
            or not 0 <= start_ns <= now_ns
            or not self.prepared
        ):
            raise ValueError("invalid episode start")
        if self._episode is not None and self._episode["result"] is None:
            if self._episode["id"] == episode_id and self._episode["start"] == start_ns:
                return
            raise ValueError("an episode is already active")
        first = {}
        for stream, history in self._history.items():
            if history and history[0][1] > 0 and start_ns < history[0][0]:
                raise ValueError("start is older than retained producer history")
            for timestamp, seq in history:
                if timestamp >= start_ns:
                    first[stream] = seq
                    break
        if self._episode is not None:
            self._closed_episodes[self._episode["id"]] = self._episode
            if len(self._closed_episodes) > 16:
                del self._closed_episodes[next(iter(self._closed_episodes))]
        self._episode = {
            "id": episode_id,
            "start": start_ns,
            "first": first,
            "result": None,
        }

    @_locked
    def end_episode(self, episode_id, end_ns, now_ns):
        episode = self._episode
        if episode is None or episode["id"] != episode_id:
            episode = self._closed_episodes.get(episode_id)
        if episode is None:
            raise ValueError("unknown episode")
        if type(end_ns) is not int or not episode["start"] <= end_ns <= now_ns:
            raise ValueError("invalid episode end")
        if episode["result"] is not None:
            if episode["end"] != end_ns:
                raise ValueError("episode end is immutable")
            return episode["result"]
        result = []
        for spec in self.descriptor.streams:
            history = self._history.get(spec.name, ())
            first = episode["first"].get(spec.name)
            if (
                first is not None
                and history
                and history[0][1] > first
                and end_ns < history[0][0]
            ):
                raise ValueError("end is older than retained producer history")
            last = next(
                (
                    seq
                    for timestamp, seq in reversed(history)
                    if episode["start"] <= timestamp <= end_ns
                ),
                None,
            )
            if last is None:
                first = None
            result.append(
                EpisodeBoundary(
                    episode_id,
                    self.descriptor.device_id,
                    spec.name,
                    self.epoch,
                    first,
                    last,
                    0 if first is None else last - first + 1,
                )
            )
        episode.update(end=end_ns, result=result)
        return result

    @_locked
    def abort_episode(self, now_ns):
        """Freeze counters on authority loss without affecting stream capture."""
        if self._episode is not None and self._episode["result"] is None:
            self.end_episode(self._episode["id"], now_ns, now_ns)


class StreamPublisher(EpisodeCounters):
    def __init__(self, descriptor):
        self.descriptor = descriptor
        self.epoch = uuid.uuid4().hex
        self.prepared = True
        self._seq = {}
        self._cached = {}
        self._sources = {}
        self._init_counters()

    @_locked
    def sample(
        self,
        stream,
        payload,
        *,
        t_sample_ns,
        t_host_rx_mono_ns,
        t_publish_mono_ns,
        source_key=None,
        origin="measured",
        valid=True,
        freshness="live",
        new_sample=True,
        clock_uncertainty_ns=0,
    ):
        spec = next(s for s in self.descriptor.streams if s.name == stream)
        if source_key is not None and self._sources.get(stream) == source_key:
            previous = self._cached[stream]
            age = (
                None
                if previous.header.t_sample_ns is None
                else t_publish_mono_ns - previous.header.t_sample_ns
            )
            stale = not valid or age is None or age >= spec.stale_after_ns
            header = replace(
                previous.header.republished(t_publish_mono_ns, stale=stale), valid=valid
            )
            return Sample(header, previous.payload)
        seq = self._seq.get(stream, 0)
        header = SampleHeader(
            self.descriptor.device_id,
            stream,
            seq,
            self.epoch,
            t_sample_ns,
            t_host_rx_mono_ns,
            t_publish_mono_ns,
            clock_uncertainty_ns=clock_uncertainty_ns,
            valid=valid,
            new_sample=new_sample,
            origin=origin,
            freshness=freshness,
        )
        value = Sample(header, payload)
        self._seq[stream] = seq + 1
        self._sources[stream] = source_key
        self._cached[stream] = value
        self.track(value)
        return value
