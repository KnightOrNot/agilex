"""Raw v3 files: typed metadata, native bytes, and verified offline replay."""

import hashlib
import json
import os
from pathlib import Path

from agilex_contract import (
    Command,
    DepthFrame,
    DeviceDescriptor,
    ImageFrame,
    JointState,
    PoseState,
    Sample,
    WrenchSample,
    from_wire,
    to_wire,
)

from .config import RecordConfig, StreamPolicy, identifier
from .safety import JointMapping, checked_positions, sample_ref


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, allow_nan=False, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def append_json(path, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, allow_nan=False, sort_keys=True) + "\n")


def write_sample(root, sample):
    h = sample.header
    directory = Path(root) / "streams" / identifier(h.device_id) / identifier(h.stream)
    directory.mkdir(parents=True, exist_ok=True)
    value = to_wire(sample)
    data = value["payload"].pop("data", None)
    if data is not None:
        image = directory / f"{h.seq:012d}.bin"
        with image.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        value["binary"] = {
            "file": str(image.relative_to(root)),
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }
    append_json(directory / "samples.jsonl", value)


def inventory(path):
    result = {}
    for file in sorted(Path(path).rglob("*")):
        if file.is_file() and file.name not in ("complete.json", "complete.json.tmp"):
            data = file.read_bytes()
            result[str(file.relative_to(path))] = {
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
    return result


def _inside(root, name):
    candidate = root / name
    if (
        Path(name).is_absolute()
        or ".." in Path(name).parts
        or any(p.is_symlink() for p in (candidate, *candidate.parents))
    ):
        raise ValueError("unsafe raw path")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError("raw path escapes episode")
    return candidate


def _read_sample(root, wire):
    binary = wire.pop("binary", None)
    if binary is not None:
        data = _inside(root, binary["file"]).read_bytes()
        if (
            len(data) != binary["size"]
            or hashlib.sha256(data).hexdigest() != binary["sha256"]
        ):
            raise ValueError("raw binary checksum mismatch")
        wire["payload"]["data"] = data
    value = from_wire(wire)
    if not isinstance(value, Sample):
        raise ValueError("raw row must contain a Sample")
    return value


def _structure(manifest):
    config = RecordConfig(**manifest["record"])
    devices = [from_wire(wire) for wire in manifest["devices"]]
    if not devices or not all(isinstance(d, DeviceDescriptor) for d in devices):
        raise ValueError("missing or invalid device descriptors")
    if len({d.device_id for d in devices}) != len(devices):
        raise ValueError("duplicate device descriptor")
    specs = {}
    for device in devices:
        identifier(device.device_id)
        for spec in device.streams:
            identifier(spec.name)
            specs[f"{device.device_id}/{spec.name}"] = spec
    policies = [StreamPolicy(**p) for p in manifest["policies"]]
    by_key = {p.key: p for p in policies}
    if len(by_key) != len(policies) or set(by_key) != set(specs):
        raise ValueError("descriptor and policy streams disagree")
    if set(manifest["streams"]) != set(specs):
        raise ValueError("descriptor and statistics streams disagree")
    if not (
        type(manifest["start_mono_ns"]) is int
        and type(manifest["end_mono_ns"]) is int
        and 0 <= manifest["start_mono_ns"] <= manifest["end_mono_ns"]
    ):
        raise ValueError("invalid episode interval")
    return config, specs, by_key


def _sample_matches(sample, spec, manifest):
    payload_types = {
        "joint": JointState,
        "pose": PoseState,
        "rgb": ImageFrame,
        "depth": DepthFrame,
        "wrench": WrenchSample,
    }
    if not isinstance(sample.payload, payload_types[spec.kind]):
        raise ValueError("sample payload disagrees with stream descriptor")
    if spec.kind == "joint" and sample.payload.names != spec.channels:
        raise ValueError("sample channels disagree with stream descriptor")
    if spec.kind in ("rgb", "depth") and sample.payload.encoding != spec.unit:
        raise ValueError("sample encoding disagrees with stream descriptor")
    info = getattr(sample.payload, "info", None)
    if info is not None:
        calibrations = (
            manifest["metadata"]
            .get("hal_metadata", {})
            .get(sample.header.device_id, {})
            .get("calibrations", {})
        )
        calibration = calibrations.get(info.calibration_id)
        if (
            calibration is None
            or hashlib.sha256(
                json.dumps(calibration, sort_keys=True, allow_nan=False).encode()
            ).hexdigest()
            != info.calibration_id
        ):
            raise ValueError("missing or inconsistent camera calibration")
        profile = calibration["depth"] if spec.kind == "depth" else calibration
        if (profile["width"], profile["height"]) != (
            sample.payload.width,
            sample.payload.height,
        ):
            raise ValueError("frame dimensions disagree with camera calibration")
        mapped = round(info.sdk_timestamp_ms * 1e6) + info.clock_offset_ns
        if abs(mapped - sample.header.t_sample_ns) > sample.header.clock_uncertainty_ns:
            raise ValueError("camera source clock disagrees with mapped sample time")


def _load(path):
    root = Path(path)
    if root.name.endswith(".partial") or root.is_symlink():
        raise ValueError("episode is incomplete")
    try:
        if (root / "failure.json").exists():
            raise ValueError("episode has a terminal failure")
        complete = json.loads((root / "complete.json").read_text())
        if complete["raw_schema_version"] != 3:
            raise ValueError("unsupported raw schema")
        if complete["files"] != inventory(root):
            raise ValueError("raw inventory mismatch")
        for name, expected in complete["files"].items():
            data = _inside(root, name).read_bytes()
            if (
                len(data) != expected["size"]
                or hashlib.sha256(data).hexdigest() != expected["sha256"]
            ):
                raise ValueError(f"raw checksum mismatch: {name}")
        manifest = json.loads((root / "manifest.json").read_text())
        if (
            manifest["episode_id"] != complete["episode_id"]
            or manifest["raw_schema_version"] != 3
        ):
            raise ValueError("episode identity/schema mismatch")
        config, specs, policies = _structure(manifest)
        samples = []
        references = {}
        for key, stats in manifest["streams"].items():
            if (
                stats["episode_id"] != manifest["episode_id"]
                or f"{stats['device_id']}/{stats['stream']}" != key
                or type(stats["required"]) is not bool
                or stats["required"] != (policies[key].role != "optional")
            ):
                raise ValueError("stream statistics identity/role mismatch")
            for field in ("received", "written", "intentional_skipped", "write_failed"):
                if type(stats[field]) is not int or stats[field] < 0:
                    raise ValueError("invalid stream counter")
            if stats["written"] + stats["intentional_skipped"] != stats["received"]:
                raise ValueError("inconsistent received stream counters")
            file = _inside(root, f"streams/{key}/samples.jsonl")
            rows = [] if not file.exists() else file.read_text().splitlines()
            if len(rows) != stats["written"]:
                raise ValueError("raw row count disagrees with completion record")
            previous = -1
            for row in rows:
                sample = _read_sample(root, json.loads(row))
                _sample_matches(sample, specs[key], manifest)
                h = sample.header
                if (
                    f"{h.device_id}/{h.stream}" != key
                    or h.stream_epoch != stats["stream_epoch"]
                    or h.seq <= previous
                ):
                    raise ValueError("raw stream identity/order mismatch")
                if (
                    stats["first_seq"] is not None
                    and not stats["first_seq"] <= h.seq <= stats["last_seq"]
                ) or not manifest["start_mono_ns"] <= h.t_sample_ns <= manifest[
                    "end_mono_ns"
                ]:
                    raise ValueError("sample outside episode boundary")
                previous = h.seq
                references[(h.device_id, h.stream, h.stream_epoch, h.seq)] = sample
                samples.append(sample)
            if stats["required"] and (
                stats["transport_lost"]
                or stats["write_failed"]
                or stats["produced"] != stats["written"] + stats["intentional_skipped"]
            ):
                raise ValueError("incomplete required stream")
            if stats["required"] and (
                not stats["produced"]
                or not stats["written"]
                or stats["produced"] != stats["last_seq"] - stats["first_seq"] + 1
                or stats["received"] != stats["produced"]
            ):
                raise ValueError("invalid producer counts")
        selections = root / "selections.jsonl"
        selected = set()
        selection_count = 0
        if selections.exists():
            last = -1
            for line in selections.read_text().splitlines():
                item = json.loads(line)
                target = item["target_mono_ns"]
                if (
                    not manifest["start_mono_ns"] <= target <= manifest["end_mono_ns"]
                    or target <= last
                ):
                    raise ValueError("invalid selection grid")
                last = target
                keys = set()
                for ref in item["samples"]:
                    identity = (
                        ref["device_id"],
                        ref["stream"],
                        ref["stream_epoch"],
                        ref["seq"],
                    )
                    if identity not in references:
                        raise ValueError("selection refers to missing sample")
                    sample = references[identity]
                    key = f"{ref['device_id']}/{ref['stream']}"
                    if key in keys:
                        raise ValueError("duplicate stream in selection")
                    keys.add(key)
                    if (
                        abs(sample.header.t_sample_ns - target)
                        > config.max_skew_ms * 1e6
                    ):
                        raise ValueError("selection sample skew exceeds limit")
                    selected.add(identity)
                if any(
                    p.role != "optional" and key not in keys
                    for key, p in policies.items()
                ):
                    raise ValueError("selection is missing a required stream")
                selection_count += 1
        if config.mode == "sampled" and (
            not selection_count or selected != set(references)
        ):
            raise ValueError("sampled episode lacks complete selection records")
        commands = _commands(root, manifest)
        return manifest, samples, commands
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid or incomplete raw episode: {exc}") from exc


def inspect_episode(path):
    manifest, samples, commands = _load(path)
    return {
        "complete": True,
        "episode_id": manifest["episode_id"],
        "mode": manifest["record"]["mode"],
        "streams": manifest["streams"],
        "samples": len(samples),
        "commands": len(commands),
    }


def replay_episode(path):
    _, samples, _ = _load(path)
    yield from sorted(
        samples,
        key=lambda s: (
            s.header.t_sample_ns,
            s.header.device_id,
            s.header.stream,
            s.header.seq,
        ),
    )


def _commands(root, manifest):
    file = root / "commands.jsonl"
    if not file.exists():
        return []
    metadata = manifest["metadata"]
    descriptors = {d.device_id: d for d in map(from_wire, manifest["devices"])}
    leader, follower = (
        descriptors[metadata["leader"]],
        descriptors[metadata["follower"]],
    )
    mapping = JointMapping(leader, follower, metadata["mapping"])
    commands = []
    previous = -1
    for line in file.read_text().splitlines():
        item = json.loads(line)
        command = from_wire(item["command"])
        observations = [from_wire(wire) for wire in item["observations"]]
        if (
            not isinstance(command, Command)
            or command.cmd_seq <= previous
            or command.session_id != metadata["session_id"]
            or command.joint_names != follower.joint_names
            or not manifest["start_mono_ns"]
            <= command.issued_mono_ns
            <= manifest["end_mono_ns"]
            or len(observations) != 4
            or not all(isinstance(s, Sample) for s in observations)
            or item["observation_refs"] != [sample_ref(s) for s in observations]
        ):
            raise ValueError("invalid command observation audit")
        master, gripper, feedback, gripper_feedback = observations
        expected_keys = [
            (leader.device_id, "joints"),
            (leader.device_id, "gripper"),
            (follower.device_id, "joints"),
            (follower.device_id, "gripper"),
        ]
        if [
            (s.header.device_id, s.header.stream) for s in observations
        ] != expected_keys:
            raise ValueError("command observation identity mismatch")
        positions = checked_positions(
            follower,
            feedback,
            mapping.target(master),
            command.issued_mono_ns,
            max_step=metadata["max_command_step_rad"],
        )
        if (
            positions != command.positions
            or command.gripper_m != gripper.payload.positions[0]
        ):
            raise ValueError(
                "recorded command does not reproduce from its observations"
            )
        previous = command.cmd_seq
        commands.append(command)
    return commands


def replay_commands(path):
    """Recompute and verify the mapping; yield commands without sending to a HAL."""
    _, _, commands = _load(path)
    yield from commands
