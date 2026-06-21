# -*- coding: utf-8 -*-
"""Configuration and data-directory validation for the desktop viewer."""

from __future__ import annotations

import json
import os
import sys
import csv
from pathlib import Path


APP_NAME = "PatientElectrodeViewer"

REQUIRED_DATA_FILES = (
    "viewer_contacts.csv",
    "viewer_bipolars.csv",
    "viewer_regions.csv",
    "viewer_patient_summary.csv",
    "viewer_data_audit.csv",
)

REQUIRED_COLUMNS = {
    "viewer_contacts.csv": {
        "patient_id",
        "contact_name",
        "shaft",
        "contact_index",
        "mni_x",
        "mni_y",
        "mni_z",
        "scs_x",
        "scs_y",
        "scs_z",
        "dk_region",
        "is_coordinate_valid",
    },
    "viewer_bipolars.csv": {
        "patient_id",
        "canonical_bipolar_key",
        "bipolar_channel",
        "anode",
        "cathode",
        "shaft",
        "mni_x",
        "mni_y",
        "mni_z",
        "brainstorm_scs_x",
        "brainstorm_scs_y",
        "brainstorm_scs_z",
        "region_bipolar",
        "region_projected",
        "dk_region_from_brainstorm_bipolar",
        "is_doctor_burned",
        "is_coordinate_valid",
    },
    "viewer_regions.csv": {
        "patient_id",
        "region_projected",
        "n_bipolars",
        "n_doctor_burned_bipolars",
        "x_centroid",
        "y_centroid",
        "z_centroid",
        "scs_x_centroid",
        "scs_y_centroid",
        "scs_z_centroid",
        "is_doctor_touched_region",
    },
    "viewer_patient_summary.csv": {
        "patient_id",
        "n_contacts",
        "n_bipolars",
        "n_shafts",
        "n_doctor_burned_bipolars",
        "n_touched_projected_regions",
        "top_doctor_region",
        "top_doctor_region_burned_count",
        "coordinate_space",
        "has_patient_surface_model",
        "surface_model_note",
    },
    "viewer_data_audit.csv": {
        "patient_id",
        "contacts",
        "contacts_missing_mni",
        "bipolars",
        "bipolars_missing_mni",
        "viewer_burned_bipolars",
        "max_abs_delta_master_vs_brainstorm_mni",
        "has_patient_surface_model",
        "n_projected_regions",
        "n_doctor_touched_regions",
        "high_surface_found",
        "n_high_source_vertices",
        "n_high_source_faces",
        "high_surface_path",
    },
}


class DataValidationError(ValueError):
    """Raised when a selected viewer data directory is not usable."""


def app_base_dir() -> Path:
    """Return the install/runtime directory for source and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def bundled_sample_data_dir() -> Path:
    return app_base_dir() / "sample_data"


def user_config_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


def config_path() -> Path:
    return user_config_dir() / "config.json"


def validate_data_dir(path: str | Path) -> Path:
    data_dir = Path(path).expanduser().resolve()
    if not data_dir.exists():
        raise DataValidationError(f"数据目录不存在：{data_dir}")
    if not data_dir.is_dir():
        raise DataValidationError(f"数据路径不是目录：{data_dir}")

    missing = [name for name in REQUIRED_DATA_FILES if not (data_dir / name).is_file()]
    if missing:
        details = "\n".join(f"- {name}" for name in missing)
        raise DataValidationError(f"数据目录缺少必需文件：\n{details}")

    column_errors = []
    for name, required_columns in REQUIRED_COLUMNS.items():
        with (data_dir / name).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
        present = {col.strip() for col in header}
        missing_columns = sorted(required_columns - present)
        if missing_columns:
            column_errors.append(f"{name}: {', '.join(missing_columns)}")
    if column_errors:
        details = "\n".join(f"- {item}" for item in column_errors)
        raise DataValidationError(f"数据文件缺少必需字段：\n{details}")
    return data_dir


def read_config() -> dict[str, str]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def write_config(data_dir: str | Path, bad_channels_path: str | Path | None = None) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, str] = {"data_dir": str(Path(data_dir).expanduser().resolve())}
    if bad_channels_path:
        payload["bad_channels_path"] = str(Path(bad_channels_path).expanduser().resolve())
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def configured_data_dir() -> Path | None:
    value = read_config().get("data_dir")
    if not value:
        sample = bundled_sample_data_dir()
        return sample if sample.exists() else None
    return Path(value).expanduser()


def configured_bad_channels_path() -> Path | None:
    value = read_config().get("bad_channels_path")
    if not value:
        return None
    return Path(value).expanduser()
