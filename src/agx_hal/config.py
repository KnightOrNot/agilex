"""Hardware deployment validation without importing any device package."""

import math

BACKENDS = {
    "sim": ("leader", "follower", "camera", "wrench"),
    "gello": ("leader",),
    "piperx": ("follower",),
    "realsense": ("camera",),
}
EFFECTS = {
    "sim": ("start_synthetic_streams",),
    "piperx": (),
    "gello": ("disable_leader_torque",),
    "realsense": ("configure_and_start_streams",),
}
POLICIES = {
    "sim": ("stop_simulated_targets", "simulated_zero"),
    "gello": ("close_serial",),
    "realsense": ("stop_and_restore_camera",),
    "piperx": ("stop_targets", "piperx_return_zero"),
}
MODULES = {
    "sim": "agx_sim",
    "piperx": "agx_hal_piperx",
    "gello": "agx_hal_gello",
    "realsense": "agx_hal_realsense",
}
FIELDS = {
    "sim": set(),
    "piperx": {
        "channel",
        "interface",
        "firmware",
        "feedback_timeout_s",
        "gripper_max_width_m",
        "gripper_force_n",
        "max_command_step_rad",
        "configure_motion_limits",
    },
    "gello": {
        "port",
        "joint_ids",
        "joint_offsets",
        "joint_signs",
        "gripper_config",
        "gripper_max_width_m",
        "feedback_timeout_s",
        "start_joints",
    },
    "realsense": {
        "serial",
        "mode",
        "width",
        "height",
        "fps",
        "warmup_frames",
        "depth_width",
        "depth_height",
        "depth_fps",
    },
}


def validate_settings(backend, settings):
    if (
        backend not in BACKENDS
        or not isinstance(settings, dict)
        or set(settings) - FIELDS[backend]
    ):
        raise ValueError("unknown backend or device settings")
    for key, value in settings.items():
        if key in ("channel", "interface", "firmware", "port", "serial", "mode"):
            if not isinstance(value, str) or not value or len(value) > 256:
                raise ValueError(f"{key} must be a nonempty string")
        elif key == "configure_motion_limits":
            if type(value) is not bool:
                raise ValueError("configure_motion_limits must be boolean")
        elif key in (
            "width",
            "height",
            "fps",
            "warmup_frames",
            "depth_width",
            "depth_height",
            "depth_fps",
        ):
            if type(value) is not int or value < (0 if key == "warmup_frames" else 1):
                raise ValueError(f"invalid {key}")
        elif key in (
            "feedback_timeout_s",
            "gripper_max_width_m",
            "gripper_force_n",
            "max_command_step_rad",
        ):
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"invalid {key}")
    if backend == "gello":
        for key in (
            "port",
            "joint_ids",
            "joint_offsets",
            "joint_signs",
            "gripper_config",
        ):
            if key not in settings:
                raise ValueError(f"GELLO requires {key}")
        ids = settings["joint_ids"]
        offsets = settings["joint_offsets"]
        signs = settings["joint_signs"]
        gripper = settings["gripper_config"]
        if (
            not isinstance(ids, (list, tuple))
            or not 1 <= len(ids) <= 32
            or len(offsets) != len(ids)
            or len(signs) != len(ids)
        ):
            raise ValueError("incompatible GELLO calibration dimensions")
        if (
            not isinstance(gripper, (list, tuple))
            or len(gripper) != 3
            or gripper[1] == gripper[2]
        ):
            raise ValueError("invalid GELLO gripper calibration")
        all_ids = [*ids, gripper[0]]
        if len(set(all_ids)) != len(all_ids) or any(
            type(n) is not int or not 0 <= n <= 252 for n in all_ids
        ):
            raise ValueError("invalid GELLO servo IDs")
        if any(
            type(v) not in (int, float) or not math.isfinite(v)
            for v in [*offsets, *gripper[1:]]
        ) or any(type(s) is not int or s not in (-1, 1) for s in signs):
            raise ValueError("invalid GELLO calibration values")
        if "start_joints" in settings:
            start = settings["start_joints"]
            if (
                not isinstance(start, (list, tuple))
                or len(start) != len(ids) + 1
                or any(
                    type(v) not in (int, float) or not math.isfinite(v) for v in start
                )
            ):
                raise ValueError("invalid GELLO start joints")
    if backend == "realsense":
        if not settings.get("serial"):
            raise ValueError("camera serial must be explicit")
        if settings.get("mode", "manual") not in ("manual", "auto", "fast", "slow"):
            raise ValueError("invalid camera profile selection mode")
    return dict(settings)
