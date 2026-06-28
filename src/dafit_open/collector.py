"""High-level collection workflow for app-style refreshes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .ble_probe import device_info, sync_training, watch_faces
from .state_export import load_app_state, write_app_state


def default_collection_dir(address: str) -> Path:
    safe_address = address.replace(":", "").lower()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path("ble-logs") / f"collect-{safe_address}-{timestamp}"


async def collect(
    address: str,
    out_dir: str | Path | None = None,
    timeout: float = 45.0,
    scan_timeout: float = 10.0,
    retries: int = 1,
    pair: bool = False,
    direct: bool = False,
    wait_timeout: float = 4.0,
    include_training: bool = True,
    training_kinds: list[str] | None = None,
    chunk_timeout: float = 8.0,
    export_state: str | Path | None = None,
    include_samples: bool = False,
) -> None:
    directory = Path(out_dir) if out_dir else default_collection_dir(address)
    directory.mkdir(parents=True, exist_ok=True)

    print(f"collecting into {directory}")
    await device_info(
        address,
        timeout=timeout,
        scan_timeout=scan_timeout,
        retries=retries,
        pair=pair,
        direct=direct,
        json_out=str(directory / "device-info.json"),
    )
    await watch_faces(
        address,
        timeout=timeout,
        scan_timeout=scan_timeout,
        retries=retries,
        pair=pair,
        direct=direct,
        wait_timeout=wait_timeout,
        json_out=str(directory / "watch-faces.json"),
    )
    if include_training:
        await sync_training(
            address,
            training_kinds or ["heart-rate"],
            timeout=timeout,
            scan_timeout=scan_timeout,
            retries=retries,
            pair=pair,
            direct=direct,
            chunk_timeout=chunk_timeout,
            json_out=str(directory / "training-sync.json"),
        )

    state_path = Path(export_state) if export_state else directory / "app-state.json"
    state = load_app_state([directory], include_samples=include_samples)
    write_app_state(state, output=state_path)
    print(f"wrote app state: {state_path}")
