"""Inspect whether this host can run the project's MLX smoke test."""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys

_AUTO = object()


def _memory_limit():
    """Return the effective container/host memory limit and its source."""
    candidates = (
        (Path("/sys/fs/cgroup/memory.max"), "cgroup-v2"),
        (Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"), "cgroup-v1"),
    )
    for path, source in candidates:
        try:
            raw = path.read_text(encoding="ascii").strip()
            if raw == "max":
                continue
            value = int(raw)
        except (OSError, ValueError):
            continue
        # cgroup v1 commonly represents "unlimited" with a huge sentinel.
        if 0 < value < 1 << 60:
            return value, source
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        value = int(pages) * int(page_size)
        if value > 0:
            return value, "host-sysconf"
    except (AttributeError, OSError, ValueError):
        pass
    return None, None


def _cpu_quota_cores():
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text(encoding="ascii").split()
        if quota != "max":
            return round(int(quota) / int(period), 3)
    except (OSError, ValueError, ZeroDivisionError):
        pass
    return None


def _distribution_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _probe_metal():
    """Probe Metal without loading model weights or running inference."""
    try:
        import mlx.core as mx

        return bool(mx.metal.is_available()), None
    except Exception as exc:  # An environment diagnostic must remain reportable.
        return None, type(exc).__name__


def inspect_environment(*, system=None, machine=None, mlx_version=_AUTO,
                        mlx_lm_version=_AUTO, metal_probe=None):
    system = system or platform.system()
    machine = machine or platform.machine()
    if mlx_version is _AUTO:
        mlx_version = _distribution_version("mlx")
    if mlx_lm_version is _AUTO:
        mlx_lm_version = _distribution_version("mlx-lm")
    metal_probe = metal_probe or _probe_metal

    apple_silicon = system == "Darwin" and machine.lower() in {"arm64", "aarch64"}
    metal_available = None
    metal_probe_error = None
    if apple_silicon and mlx_version is not None:
        metal_available, metal_probe_error = metal_probe()

    blockers = []
    if not apple_silicon:
        blockers.append("The selected MLX training path requires macOS on Apple Silicon.")
    if mlx_version is None:
        blockers.append("The mlx package is not installed.")
    if mlx_lm_version is None:
        blockers.append("The mlx-lm package is not installed.")
    if apple_silicon and mlx_version is not None and metal_available is not True:
        blockers.append("Apple Metal availability could not be verified.")
    if metal_probe_error:
        blockers.append(f"The Metal probe failed with {metal_probe_error}.")

    memory_bytes, memory_source = _memory_limit()
    return {
        "system": system,
        "machine": machine,
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "cpu_quota_cores": _cpu_quota_cores(),
        "memory_limit_bytes": memory_bytes,
        "memory_limit_source": memory_source,
        "mlx_version": mlx_version,
        "mlx_lm_version": mlx_lm_version,
        "metal_available": metal_available,
        "model_loaded": False,
        "smoke_test_ready": apple_silicon and mlx_version is not None and
                            mlx_lm_version is not None and metal_available is True,
        "blockers": blockers,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(inspect_environment(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
