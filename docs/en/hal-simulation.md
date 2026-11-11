# HAL contracts and hardware-free simulation (P1)

English | [简体中文](../zh/hal-simulation.md)

P1 provides the independent `agilex-contract` package and synthetic Leader, Follower, RGB-D camera and six-axis force/torque HALs. Each device runs in its own process over local IPC using the same contract. Existing CLI/browser workflows still use their original implementations; the new runtime's recording, replay and physical HALs are not part of this stage.

## Working copy and installation

`third-party/agilex-contract` is an independent Git submodule pinned to an exact commit and referenced through a uv local path. Initialize all submodules when obtaining the test candidate. The original five submodule commits are unchanged. Root version 0.2.2 and contract version 0.1.0 are dev snapshots awaiting physical-device acceptance.

To obtain the test candidate on another computer:

```bash
git clone --branch dev --recurse-submodules git@github.com:KnightOrNot/agilex.git
cd agilex
make sync
uv run --frozen agx-sim --help
make verify
```

For an existing checkout, preserve local changes first, then update:

```bash
git switch dev
git pull --ff-only origin dev
git submodule sync --recursive
git submodule update --init --recursive
make sync
```

These steps prepare the root environment and P1 simulation. Before using the existing physical-device CLI/Web workflows, follow the [installation guide](installation.md) to synchronize the separate SDK, GELLO, camera, converter and browser environments. Preserve the test computer's device configuration and calibration. `agx-sim` does not control physical devices.

`make verify` includes contract tests, simulated authority tests, real child-process IPC and existing regression tests. No physical devices are accessed. The OS must permit local test sockets; sandbox bind failures do not indicate a hardware fault.

## Start and read

Start a synthetic camera in one terminal and inspect the same endpoint directory in another:

```bash
uv run --frozen agx-sim serve --kind camera --device-id front --endpoint-dir /tmp/agx-front
```

```bash
uv run --frozen agx-sim inspect --endpoint-dir /tmp/agx-front
```

The directory must belong to the current user with mode 0700; sockets use 0600. The server refuses to replace existing endpoints. Ctrl+C/SIGTERM removes sockets created by this process. A forced kill may leave endpoints; investigate ownership before handling them instead of automatically removing unknown resources.

Discovery returns a descriptor without starting streams. Acquire a lease and PREPARE before reading samples:

```python
from agx_sim.transport import HalClient

with HalClient("/tmp/agx-front") as client:
    owner = {"session_id": "demo"}
    owner.update(client.request("acquire", **owner))
    client.request("prepare", **owner)
    for _ in range(6):
        sample = client.receive(0.5)
        if sample is not None:
            print(sample.header.device_id, sample.header.stream, sample.header.seq)
    client.request("release", **owner)
```

`--kind` supports `leader`, `follower`, `camera` and `wrench`. Different device IDs and endpoint directories allow another camera or force sensor without changing the consumer protocol. A Follower with `--axes 2` exercises a contract independent of six-axis/seven-value assumptions. Images are synthetic 8×6 frames for protocol acceptance, not real-device throughput measurements.

## Authority and time semantics

A Follower requires acquire, prepare, authorize, align_begin, align_step and activate before continuous commands. Pass an `agilex_contract.Command` to `align_step`; channel names/order must match the descriptor, targets must respect limits, and timestamps use local `time.monotonic_ns()`. Simulated alignment updates synthetic state immediately and does not prove physical arrival.

`HalClient.send(command)` sends continuous targets without blocking; False means the connection is not ready or the queue is temporarily unavailable. Management, continuous commands and sample/acknowledgement streams use separate sockets. Acknowledgements are received/accepted/submitted/rejected, never physical execution claims. Pending targets use latest-wins replacement with another expiry check before submission. Each turn handles a bounded batch; a remaining receive backlog defers submission to avoid intermediate stale targets while management, watchdogs and sampling continue.

Polling waits according to the next sampling deadline. `--hz` specifies the target rate; Python and OS scheduling do not guarantee hard real-time performance. Message size, types and nesting depth are bounded; rejecting malformed input leaves the service available for subsequent requests.

The service independently detects command deadlines, lease expiry, alignment step gaps and overall alignment deadlines. Status queries, rejected commands and lease renewal do not refresh command deadlines. Expiry discards pending targets and revokes authority; reacquisition still requires authorization and alignment. `--command-timeout-s` and `--lease-timeout-s` are simulation settings, not verified PiPER-X policies.

Samples carry device/stream/epoch/sequence, sample/receive/publish times, clock domain, validity and provenance. Synthetic samples are estimated; cached samples retain their original sampling time and sequence and become cached/stale. RGB8 and native little-endian Z16 use separate binary frames with depth scale retained. Wrench samples include a coordinate frame, torque reference point, zero bias and calibration ID.

PUB/SUB may lose messages; received sequences expose gaps. P1 defines episode boundary fields; full recording, producer-boundary reconciliation and completion records belong to P2. P1 message round trips are not full collection acceptance.
