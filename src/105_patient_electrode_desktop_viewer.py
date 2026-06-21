# -*- coding: utf-8 -*-
r"""Desktop VTK/PyVista viewer for patient SEEG electrodes.

Run:
    python src\105_patient_electrode_desktop_viewer.py --data-dir sample_data

This desktop viewer reads a user-selected local viewer_data directory.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyvista as pv
os.environ.setdefault("QT_API", "pyqt5")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
from pyvistaqt import QtInteractor
from qtpy import QtCore, QtWidgets

from patient_electrode_viewer_config import (
    DataValidationError,
    configured_bad_channels_path,
    configured_data_dir,
    validate_data_dir,
    write_config,
)

APP_TITLE = "患者电极桌面查看器"

COLORWAY = [
    "#4f8cff", "#00a884", "#f0a202", "#d95d39", "#7b61ff", "#20a4f3", "#a23e48", "#18a999",
    "#9b5de5", "#f15bb5", "#00bbf9", "#fee440", "#00f5d4", "#b56576", "#6d597a", "#355070",
]
BAD_CHANNEL_COLOR = "#7c3aed"
BAD_CHANNEL_LABEL_BG = "#ede9fe"

LAYER_LABELS = {
    "surface": "脑表面",
    "contacts": "单极触点",
    "bipolars": "双极中点",
    "burned": "烧毁双极",
    "bad_contacts": "坏导触点",
    "bad_bipolars": "坏导双极",
    "shaft_lines": "电极轨迹",
    "shaft_labels": "轨迹名称",
    "electrode_labels": "电极标签",
    "selected_regions": "脑区表面",
    "region_centroids": "烧毁双极重心",
}

DEFAULT_LAYER_CHECKED = {
    "shaft_labels": False,
    "electrode_labels": False,
}

DYNAMIC_LAYERS = {
    "contacts",
    "contact_labels",
    "bipolars",
    "bipolar_labels",
    "burned",
    "bad_contacts",
    "bad_contact_labels",
    "bad_bipolars",
    "bad_bipolar_labels",
    "shaft_lines",
    "shaft_labels",
    "electrode_labels",
    "selected_regions",
    "region_centroids",
    "manual_selection",
    "pick_highlight",
}

APP_STYLE = """
QMainWindow, QWidget {
    background: #f5f7fb;
    color: #172033;
    font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
}
QScrollArea {
    border: none;
    background: #eef2f7;
}
QFrame#sectionCard {
    background: #ffffff;
    border: 1px solid #d9e1ec;
    border-radius: 12px;
}
QLabel#sectionTitle {
    background: transparent;
    color: #172033;
    font-size: 14px;
    font-weight: 700;
    padding: 0 0 2px 0;
}
QLabel[fieldLabel="true"] {
    background: transparent;
    color: #506079;
    font-size: 12px;
    font-weight: 600;
    padding: 0 0 0 1px;
}
QLabel {
    color: #314057;
}
QComboBox, QLineEdit, QPlainTextEdit, QListWidget {
    background: #ffffff;
    border: 1px solid #cfd8e6;
    border-radius: 8px;
    padding: 7px 9px;
    selection-background-color: #2f6feb;
}
QComboBox:hover, QLineEdit:hover, QPlainTextEdit:hover, QListWidget:hover {
    border-color: #8fb3e8;
}
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QListWidget:focus {
    border: 1px solid #2f6feb;
}
QCheckBox {
    spacing: 9px;
    color: #24324a;
}
QPushButton {
    background: #e9eef7;
    color: #203047;
    border: 1px solid #ccd6e5;
    border-radius: 9px;
    padding: 9px 12px;
    font-weight: 600;
}
QPushButton:hover {
    background: #dfe8f7;
    border-color: #9eb9e6;
}
QPushButton#primaryButton {
    background: #2563eb;
    color: white;
    border-color: #2563eb;
}
QPushButton#primaryButton:hover {
    background: #1d4ed8;
}
QLabel#statsCard, QLabel#detailCard {
    background: #ffffff;
    border: 1px solid #d9e1ec;
    border-radius: 12px;
    padding: 12px 14px;
}
QTableWidget {
    background: #ffffff;
    alternate-background-color: #f7f9fc;
    border: 1px solid #d9e1ec;
    border-radius: 12px;
    gridline-color: #e3e9f2;
    selection-background-color: #dbeafe;
    selection-color: #111827;
}
QHeaderView::section {
    background: #eef3f9;
    color: #1f2a3d;
    border: none;
    border-right: 1px solid #d9e1ec;
    padding: 8px 10px;
    font-weight: 700;
}
"""


def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False, **kwargs)


def clean_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value)
    return "" if text.lower() == "nan" else text


def project_display_region(value: object) -> str:
    excluded = ("white", "csf", "cerebrospinal", "ventricle", "unknown", "nan")
    parts = []
    for part in clean_str(value).split("|"):
        region = part.strip()
        if not region:
            continue
        low = region.lower()
        if any(token in low for token in excluded):
            continue
        parts.append(region)
    return "|".join(dict.fromkeys(parts))


def normalize_dk_surface_label(label: object) -> str:
    text = str(label).lower().strip()
    aliases = {
        "caudal ant cing": "caudalanteriorcingulate",
        "caudal mid front": "caudalmiddlefrontal",
        "rostral ant cing": "rostralanteriorcingulate",
        "rostral mid front": "rostralmiddlefrontal",
    }
    for src, dst in aliases.items():
        text = text.replace(src, dst)
    return re.sub(r"[^a-z0-9]+", "", text)


def parse_selection(text: str | None) -> set[str]:
    if not text:
        return set()
    return {part.upper() for part in re.split(r"[,;，；\s]+", text.strip()) if part}


def normalize_contact_name(value: object) -> str:
    return clean_str(value).upper().replace(" ", "")


def contact_sort_key(value: object) -> tuple[str, int, str]:
    text = normalize_contact_name(value)
    match = re.match(r"^([A-Z]+)(\d+)(.*)$", text)
    if match:
        return match.group(1), int(match.group(2)), match.group(3)
    return text, -1, ""


def canonical_bipolar_name(value: object) -> str:
    parts = [normalize_contact_name(part) for part in re.split(r"\s*-\s*", clean_str(value)) if normalize_contact_name(part)]
    if len(parts) != 2:
        return normalize_contact_name(value)
    return "-".join(sorted(parts, key=contact_sort_key))


def hex_to_rgb_float(color: str) -> tuple[float, float, float]:
    color = color.strip().lstrip("#")
    return tuple(int(color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb_float_to_hex(color: object) -> str:
    arr = np.asarray(color, dtype=float).ravel()
    if arr.size < 3:
        return "#ffc21a"
    vals = np.clip(arr[:3], 0.0, 1.0)
    return "#" + "".join(f"{int(round(x * 255)):02x}" for x in vals)


def make_polydata(vertices: np.ndarray, faces: np.ndarray) -> pv.PolyData:
    faces = np.asarray(faces, dtype=np.int64)
    vtk_faces = np.column_stack([np.full(faces.shape[0], 3, dtype=np.int64), faces]).ravel()
    return pv.PolyData(np.asarray(vertices, dtype=float), vtk_faces)


@dataclass
class SurfaceBundle:
    cortex: pv.PolyData
    cortex_vertices: np.ndarray
    cortex_faces: np.ndarray
    dk_scouts_by_norm: dict[str, dict[str, object]]
    aseg: pv.PolyData | None
    aseg_vertices: np.ndarray
    aseg_faces: np.ndarray
    aseg_scouts_by_norm: dict[str, dict[str, object]]


@dataclass
class PatientViewState:
    selected_regions: set[str]
    selected_shafts: set[str]
    region_filter: str = ""
    region_source: str = "combined"
    selected_regions_by_source: dict[str, set[str]] | None = None
    restrict_to_regions: bool = False
    manual_selection: str = ""
    selected_only: bool = False
    camera_by_mode: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.camera_by_mode is None:
            self.camera_by_mode = {}
        if self.selected_regions_by_source is None:
            self.selected_regions_by_source = {"combined": set(self.selected_regions), "brainstorm": set()}


class SurfaceLoadWorker(QtCore.QObject):
    finished = QtCore.Signal(str, object)
    failed = QtCore.Signal(str, str)

    def __init__(self, data: "DataStore", patient: str) -> None:
        super().__init__()
        self.data = data
        self.patient = patient

    @QtCore.Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self.patient, self.data.surface(self.patient))
        except Exception as exc:
            self.failed.emit(self.patient, f"{type(exc).__name__}: {exc}")


class NoWheelComboBox(QtWidgets.QComboBox):
    def wheelEvent(self, event: object) -> None:
        event.ignore()


class DataStore:
    def __init__(self, data_dir: Path, bad_channels_path: Path | None = None) -> None:
        self.data_dir = validate_data_dir(data_dir)
        self.surface_dir = self.data_dir / "surfaces"
        self.bad_channels_path = bad_channels_path
        self.contacts = read_csv(self.data_dir / "viewer_contacts.csv")
        self.bipolars = read_csv(self.data_dir / "viewer_bipolars.csv")
        self.regions = read_csv(self.data_dir / "viewer_regions.csv")
        self.summary = read_csv(self.data_dir / "viewer_patient_summary.csv")
        self.audit = read_csv(self.data_dir / "viewer_data_audit.csv")
        for df in (self.contacts, self.bipolars, self.regions, self.summary, self.audit):
            if "patient_id" in df.columns:
                df["patient_id"] = df["patient_id"].astype(str)
        for col in ["is_doctor_burned", "is_coordinate_valid", "same_region"]:
            if col in self.bipolars.columns:
                self.bipolars[col] = self.bipolars[col].astype(str).str.lower().isin(["true", "1"])
        self.contacts["contact_norm_for_bad"] = self.contacts["contact_name"].map(normalize_contact_name)
        self.bipolars["canonical_bad_key"] = self.bipolars["canonical_bipolar_key"].map(canonical_bipolar_name)
        self.contacts["is_bad_contact"] = False
        self.contacts["bad_contact_sources"] = ""
        self.bipolars["is_bad_bipolar"] = False
        self.bipolars["bad_bipolar_sources"] = ""
        self.load_bad_channel_flags()
        self.bipolars["region_combined"] = self.bipolars.get("region_projected", "").map(project_display_region)
        self.bipolars["region_brainstorm"] = self.bipolars.get("dk_region_from_brainstorm_bipolar", "").map(project_display_region)
        if "is_doctor_touched_region" in self.regions.columns:
            self.regions["is_doctor_touched_region"] = self.regions["is_doctor_touched_region"].astype(str).str.lower().isin(["true", "1"])
        self.patients = sorted(self.bipolars["patient_id"].dropna().astype(str).unique())
        self.surface_cache: dict[str, SurfaceBundle] = {}

    def load_bad_channel_flags(self) -> None:
        if self.bad_channels_path is None or not self.bad_channels_path.exists():
            return
        try:
            bad_contacts = pd.read_excel(self.bad_channels_path, sheet_name="bad_channels")
            bad_bipolars = pd.read_excel(self.bad_channels_path, sheet_name="bad_bipolar_channels")
        except Exception:
            return

        if not bad_contacts.empty:
            contacts = bad_contacts.copy()
            contacts["patient_id"] = contacts["patient"].astype(str).str.strip()
            contacts["contact_norm_for_bad"] = contacts["normalized_contact_name"].map(normalize_contact_name)
            contact_sources = (
                contacts.groupby(["patient_id", "contact_norm_for_bad"], dropna=False)
                .agg(
                    bad_contact_sources=(
                        "source_bipolar_label",
                        lambda s: "; ".join(sorted({clean_str(x) for x in s if clean_str(x)})),
                    )
                )
                .reset_index()
            )
            self.contacts = self.contacts.merge(contact_sources, on=["patient_id", "contact_norm_for_bad"], how="left", suffixes=("", "_loaded"))
            loaded_col = "bad_contact_sources_loaded"
            if loaded_col in self.contacts.columns:
                self.contacts["bad_contact_sources"] = self.contacts[loaded_col].fillna("")
                self.contacts = self.contacts.drop(columns=[loaded_col])
            self.contacts["is_bad_contact"] = self.contacts["bad_contact_sources"].astype(str).str.len().gt(0)

        if not bad_bipolars.empty:
            bipolars = bad_bipolars.copy()
            bipolars["patient_id"] = bipolars["patient"].astype(str).str.strip()
            if {"anode_contact", "cathode_contact"}.issubset(bipolars.columns):
                bipolars["canonical_bad_key"] = bipolars.apply(
                    lambda row: canonical_bipolar_name(f"{row['anode_contact']}-{row['cathode_contact']}"),
                    axis=1,
                )
            else:
                bipolars["canonical_bad_key"] = bipolars["bad_bipolar_label"].map(canonical_bipolar_name)
            bipolar_sources = (
                bipolars.groupby(["patient_id", "canonical_bad_key"], dropna=False)
                .agg(
                    bad_bipolar_sources=(
                        "source",
                        lambda s: "; ".join(sorted({clean_str(x) for x in s if clean_str(x)})),
                    ),
                    bad_bipolar_labels=(
                        "bad_bipolar_label",
                        lambda s: "; ".join(sorted({clean_str(x) for x in s if clean_str(x)})),
                    ),
                )
                .reset_index()
            )
            self.bipolars = self.bipolars.merge(bipolar_sources, on=["patient_id", "canonical_bad_key"], how="left", suffixes=("", "_loaded"))
            for col in ["bad_bipolar_sources", "bad_bipolar_labels"]:
                loaded_col = f"{col}_loaded"
                if loaded_col in self.bipolars.columns:
                    self.bipolars[col] = self.bipolars[loaded_col].fillna("")
                    self.bipolars = self.bipolars.drop(columns=[loaded_col])
            if "bad_bipolar_labels" not in self.bipolars.columns:
                self.bipolars["bad_bipolar_labels"] = ""
            self.bipolars["is_bad_bipolar"] = self.bipolars["bad_bipolar_sources"].astype(str).str.len().gt(0)

    def surface(self, patient: str) -> SurfaceBundle:
        if patient in self.surface_cache:
            return self.surface_cache[patient]
        cortex_path = self.surface_dir / f"{patient}_cortex_pial_high.npz"
        if not cortex_path.exists():
            cortex_path = self.surface_dir / f"{patient}_cortex_pial_low.npz"
        if not cortex_path.exists():
            raise FileNotFoundError(f"未找到 {patient} 的脑表面 npz：{self.surface_dir}")
        cortex_npz = np.load(cortex_path)
        vertices = np.asarray(cortex_npz["vertices_scs_mm"], dtype=np.float32)
        faces = np.asarray(cortex_npz["faces"], dtype=np.int32)
        scouts_path = self.surface_dir / f"{patient}_desikan_killiany_scouts_high.json"
        if not scouts_path.exists():
            scouts_path = self.surface_dir / f"{patient}_desikan_killiany_scouts.json"
        if scouts_path.exists():
            raw_dk_scouts = json.loads(scouts_path.read_text(encoding="utf-8"))
            dk_scouts = [
                {
                    "label": str(scout.get("label", "")),
                    "normalized_label": str(scout.get("normalized_label", "")),
                    "vertices": np.asarray(scout.get("vertices", []), dtype=np.int32),
                    "color": np.asarray(scout.get("color", [0.72, 0.72, 0.72]), dtype=float),
                }
                for scout in raw_dk_scouts
            ]
        else:
            dk_scouts = []

        aseg_vertices = np.empty((0, 3), dtype=np.float32)
        aseg_faces = np.empty((0, 3), dtype=np.int32)
        aseg_scouts: list[dict[str, object]] = []
        aseg_poly = None
        aseg_path = self.surface_dir / f"{patient}_aseg_structures.npz"
        aseg_scouts_path = self.surface_dir / f"{patient}_aseg_structure_scouts.json"
        if aseg_path.exists():
            aseg_npz = np.load(aseg_path)
            aseg_vertices = np.asarray(aseg_npz["vertices_scs_mm"], dtype=np.float32)
            aseg_faces = np.asarray(aseg_npz["faces"], dtype=np.int32)
            if aseg_vertices.size and aseg_faces.size:
                aseg_poly = make_polydata(aseg_vertices, aseg_faces)
        if aseg_scouts_path.exists():
            raw = json.loads(aseg_scouts_path.read_text(encoding="utf-8"))
            for scout in raw:
                aseg_scouts.append(
                    {
                        "label": str(scout.get("label", "")),
                        "normalized_label": str(scout.get("normalized_label", "")),
                        "vertices": np.asarray(scout.get("vertices", []), dtype=np.int32),
                        "color": np.asarray(scout.get("color", [1.0, 0.75, 0.1]), dtype=float),
                    }
                )

        bundle = SurfaceBundle(
            cortex=make_polydata(vertices, faces),
            cortex_vertices=vertices,
            cortex_faces=faces,
            dk_scouts_by_norm={str(s["normalized_label"]): s for s in dk_scouts},
            aseg=aseg_poly,
            aseg_vertices=aseg_vertices,
            aseg_faces=aseg_faces,
            aseg_scouts_by_norm={str(s["normalized_label"]): s for s in aseg_scouts},
        )
        self.surface_cache[patient] = bundle
        return bundle


class DesktopViewer(QtWidgets.QMainWindow):
    def __init__(self, data_dir: Path, bad_channels_path: Path | None = None) -> None:
        super().__init__()
        self.data_dir = validate_data_dir(data_dir)
        self.bad_channels_path = bad_channels_path
        self.data = DataStore(self.data_dir, self.bad_channels_path)
        self.actors: dict[str, list[object]] = {}
        self.patient_states: dict[str, PatientViewState] = {}
        self.surface_threads: dict[str, tuple[QtCore.QThread, SurfaceLoadWorker]] = {}
        self.loading_dialog: QtWidgets.QProgressDialog | None = None
        self._reset_camera_after_surface_load = False
        self.selected_pick_key: tuple[str, str] | None = None
        self.current_bipolars = pd.DataFrame()
        self.current_contacts = pd.DataFrame()
        self.current_patient = self.data.patients[0]
        self._reset_camera_next_refresh = True
        self.setWindowTitle(f"{APP_TITLE} - VTK 高分辨率版")
        self.resize(1680, 980)
        self._build_ui()
        self._connect()
        self.restore_patient_state(self.current_patient)
        self.populate_regions()
        self.populate_shafts()
        self.refresh_all()

    def _build_ui(self) -> None:
        self.setStyleSheet(APP_STYLE)
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        side = QtWidgets.QScrollArea()
        side.setWidgetResizable(True)
        side.setFixedWidth(390)
        panel = QtWidgets.QWidget()
        side.setWidget(panel)
        form = QtWidgets.QVBoxLayout(panel)
        form.setContentsMargins(14, 12, 14, 12)
        form.setSpacing(14)

        def add_section(title: str) -> QtWidgets.QVBoxLayout:
            box = QtWidgets.QFrame()
            box.setObjectName("sectionCard")
            section = QtWidgets.QVBoxLayout(box)
            section.setContentsMargins(16, 14, 16, 16)
            section.setSpacing(10)
            title_label = QtWidgets.QLabel(title)
            title_label.setObjectName("sectionTitle")
            section.addWidget(title_label)
            form.addWidget(box)
            return section

        def label(text: str) -> QtWidgets.QLabel:
            widget = QtWidgets.QLabel(text)
            widget.setProperty("fieldLabel", True)
            return widget

        view_section = add_section("病例视图")

        self.data_dir_label = QtWidgets.QLabel(str(self.data_dir))
        self.data_dir_label.setWordWrap(True)
        self.data_dir_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.change_data_dir_btn = QtWidgets.QPushButton("更换数据目录")
        view_section.addWidget(label("数据目录"))
        view_section.addWidget(self.data_dir_label)
        view_section.addWidget(self.change_data_dir_btn)

        self.patient_combo = NoWheelComboBox()
        self.patient_combo.addItems(self.data.patients)
        view_section.addWidget(label("当前患者"))
        view_section.addWidget(self.patient_combo)

        self.coord_combo = NoWheelComboBox()
        self.coord_combo.addItems(["个体脑表面（Brainstorm SCS）", "MNI 点云"])
        view_section.addWidget(label("显示空间"))
        view_section.addWidget(self.coord_combo)

        self.color_combo = NoWheelComboBox()
        self.color_combo.addItems(["按烧毁状态", "按脑区", "按轨迹", "按可疑度"])
        view_section.addWidget(label("双极颜色"))
        view_section.addWidget(self.color_combo)

        layer_section = add_section("显示内容")
        self.layer_checks: dict[str, QtWidgets.QCheckBox] = {}
        for key, text in LAYER_LABELS.items():
            cb = QtWidgets.QCheckBox(text)
            cb.setChecked(DEFAULT_LAYER_CHECKED.get(key, True))
            self.layer_checks[key] = cb
            layer_section.addWidget(cb)

        region_section = add_section("脑区定位")
        self.region_source_combo = NoWheelComboBox()
        self.region_source_combo.addItems(["结合版（两端）", "Brainstorm版（中点）"])
        region_section.addWidget(label("脑区来源"))
        region_section.addWidget(self.region_source_combo)
        self.region_filter = QtWidgets.QLineEdit()
        self.region_filter.setPlaceholderText("输入关键词过滤脑区")
        self.region_list = QtWidgets.QListWidget()
        self.region_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.region_list.setMinimumHeight(210)
        region_section.addWidget(self.region_filter)
        region_section.addWidget(self.region_list)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        self.apply_regions_btn = QtWidgets.QPushButton("应用高亮")
        self.apply_regions_btn.setObjectName("primaryButton")
        self.clear_regions_btn = QtWidgets.QPushButton("清空选择")
        row.addWidget(self.apply_regions_btn)
        row.addWidget(self.clear_regions_btn)
        region_section.addLayout(row)
        self.restrict_to_regions_check = QtWidgets.QCheckBox("仅看选中脑区电极")
        self.restrict_to_regions_check.setChecked(False)
        region_section.addWidget(self.restrict_to_regions_check)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        region_section.addWidget(self.status_label)

        filter_section = add_section("电极筛选")
        self.shaft_list = QtWidgets.QListWidget()
        self.shaft_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.shaft_list.setMinimumHeight(140)
        filter_section.addWidget(label("轨迹筛选"))
        filter_section.addWidget(self.shaft_list)

        self.selection_text = QtWidgets.QPlainTextEdit()
        self.selection_text.setPlaceholderText("例如：I8-I9, A10-A11, A1, I9")
        self.selection_text.setFixedHeight(82)
        filter_section.addWidget(label("指定电极或触点"))
        filter_section.addWidget(self.selection_text)
        self.selected_only_check = QtWidgets.QCheckBox("仅看指定电极")
        filter_section.addWidget(self.selected_only_check)
        form.addStretch(1)

        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        self.stats_label = QtWidgets.QLabel("")
        self.stats_label.setObjectName("statsCard")
        self.stats_label.setWordWrap(True)
        right_layout.addWidget(self.stats_label)
        self.plotter = QtInteractor(right)
        self.plotter.set_background("white")
        self.plotter.interactor.setMinimumHeight(560)
        self.plotter.interactor.installEventFilter(self)
        self.plotter.interactor.setMouseTracking(True)
        right_layout.addWidget(self.plotter.interactor, stretch=1)
        self.detail_label = QtWidgets.QLabel("点击/选择电极后在这里查看明细")
        self.detail_label.setObjectName("detailCard")
        self.detail_label.setWordWrap(True)
        right_layout.addWidget(self.detail_label)
        self.table = QtWidgets.QTableWidget()
        self.table.setMinimumHeight(240)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        right_layout.addWidget(self.table)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(side)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([390, 1290])
        layout.addWidget(splitter)

    def _connect(self) -> None:
        self.patient_combo.currentTextChanged.connect(self.on_patient_changed)
        self.coord_combo.currentIndexChanged.connect(self.on_coordinate_changed)
        self.color_combo.currentIndexChanged.connect(self.refresh_data_layers)
        for key, cb in self.layer_checks.items():
            cb.stateChanged.connect(lambda _state, layer=key: self.on_layer_changed(layer))
        self.region_source_combo.currentIndexChanged.connect(self.on_region_source_changed)
        self.region_filter.textChanged.connect(self.populate_regions)
        self.apply_regions_btn.clicked.connect(self.on_regions_applied)
        self.clear_regions_btn.clicked.connect(self.clear_regions)
        self.restrict_to_regions_check.stateChanged.connect(self.on_filters_changed)
        self.shaft_list.itemSelectionChanged.connect(self.on_filters_changed)
        self.selection_text.textChanged.connect(self.on_manual_selection_changed)
        self.selected_only_check.stateChanged.connect(self.on_filters_changed)
        self.table.itemSelectionChanged.connect(self.on_table_selection)
        self.change_data_dir_btn.clicked.connect(self.choose_data_dir)

    def eventFilter(self, watched: object, event: object) -> bool:
        if hasattr(self, "plotter") and watched is self.plotter.interactor:
            if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.RightButton:
                pos = event.position() if hasattr(event, "position") else event.pos()
                self.on_3d_qt_right_click(np.array([float(pos.x()), float(pos.y())], dtype=float))
                return True
        return super().eventFilter(watched, event)

    def choose_data_dir(self) -> None:
        selected = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "选择 viewer_data 数据目录",
            str(self.data_dir),
        )
        if not selected:
            return
        try:
            self.load_data_dir(Path(selected))
        except Exception as exc:
            self.show_error("数据目录不可用", f"{type(exc).__name__}: {exc}")

    def load_data_dir(self, data_dir: Path) -> None:
        new_data = DataStore(data_dir, self.bad_channels_path)
        self.data = new_data
        self.data_dir = new_data.data_dir
        write_config(self.data_dir, self.bad_channels_path)
        self.patient_states.clear()
        self.actors.clear()
        self.surface_threads.clear()
        self.current_bipolars = pd.DataFrame()
        self.current_contacts = pd.DataFrame()
        self.current_patient = self.data.patients[0]
        self.data_dir_label.setText(str(self.data_dir))
        self.patient_combo.blockSignals(True)
        self.patient_combo.clear()
        self.patient_combo.addItems(self.data.patients)
        self.patient_combo.setCurrentText(self.current_patient)
        self.patient_combo.blockSignals(False)
        self._reset_camera_next_refresh = True
        self.restore_patient_state(self.current_patient)
        self.populate_regions()
        self.populate_shafts()
        self.refresh_all()

    def on_patient_changed(self, patient: str) -> None:
        self.save_patient_state(self.current_patient)
        self.current_patient = patient
        self._reset_camera_next_refresh = True
        self.restore_patient_state(patient)
        self.populate_regions()
        self.populate_shafts()
        self.refresh_all()

    def on_coordinate_changed(self) -> None:
        self.save_patient_state(self.current_patient)
        self._reset_camera_next_refresh = True
        self.refresh_all()

    def state_for(self, patient: str) -> PatientViewState:
        if patient not in self.patient_states:
            self.patient_states[patient] = PatientViewState(set(), set())
        return self.patient_states[patient]

    def save_patient_state(self, patient: str) -> None:
        if not patient or not hasattr(self, "region_list"):
            return
        state = self.state_for(patient)
        mode = self.region_source_mode()
        state.region_source = mode
        if state.selected_regions_by_source is None:
            state.selected_regions_by_source = {}
        state.selected_regions_by_source[mode] = set(self.selected_regions())
        state.selected_regions = set(self.selected_regions())
        state.selected_shafts = set(self.selected_shafts())
        state.region_filter = self.region_filter.text()
        state.restrict_to_regions = self.restrict_to_regions_check.isChecked()
        state.manual_selection = self.selection_text.toPlainText()
        state.selected_only = self.selected_only_check.isChecked()
        if hasattr(self, "plotter") and state.camera_by_mode is not None:
            try:
                state.camera_by_mode[self.coordinate_mode()] = self.plotter.camera_position
            except Exception:
                pass

    def restore_patient_state(self, patient: str) -> None:
        state = self.state_for(patient)
        if state.selected_regions_by_source is None:
            state.selected_regions_by_source = {"combined": set(state.selected_regions), "brainstorm": set()}
        region_source_index = 1 if state.region_source == "brainstorm" else 0
        self.region_source_combo.blockSignals(True)
        self.region_filter.blockSignals(True)
        self.restrict_to_regions_check.blockSignals(True)
        self.selection_text.blockSignals(True)
        self.selected_only_check.blockSignals(True)
        self.region_source_combo.setCurrentIndex(region_source_index)
        self.region_filter.setText(state.region_filter)
        self.restrict_to_regions_check.setChecked(state.restrict_to_regions)
        self.selection_text.setPlainText(state.manual_selection)
        self.selected_only_check.setChecked(state.selected_only)
        self.region_source_combo.blockSignals(False)
        self.region_filter.blockSignals(False)
        self.restrict_to_regions_check.blockSignals(False)
        self.selection_text.blockSignals(False)
        self.selected_only_check.blockSignals(False)

    def on_regions_applied(self) -> None:
        self.save_patient_state(self.current_patient)
        self.refresh_data_layers()

    def on_region_source_changed(self) -> None:
        state = self.state_for(self.current_patient)
        previous_mode = state.region_source
        if state.selected_regions_by_source is None:
            state.selected_regions_by_source = {}
        state.selected_regions_by_source[previous_mode] = set(self.selected_regions())
        state.region_source = self.region_source_mode()
        self.populate_regions()
        self.save_patient_state(self.current_patient)
        self.refresh_data_layers()

    def on_filters_changed(self) -> None:
        self.save_patient_state(self.current_patient)
        self.refresh_data_layers()

    def on_manual_selection_changed(self) -> None:
        self.save_patient_state(self.current_patient)
        if self.selected_only_check.isChecked():
            self.refresh_data_layers()
        else:
            self.refresh_manual_selection_layer()

    def add_layer_actor(self, layer: str, actor: object) -> None:
        if actor is None:
            return
        self.actors.setdefault(layer, []).append(actor)
        visible = self.actor_layer_visible(layer)
        if hasattr(actor, "SetVisibility"):
            actor.SetVisibility(bool(visible))

    def actor_layer_visible(self, layer: str) -> bool:
        if layer == "contact_labels":
            return self.layer_checks["electrode_labels"].isChecked() and self.layer_checks["contacts"].isChecked()
        if layer == "bipolar_labels":
            return self.layer_checks["electrode_labels"].isChecked() and self.layer_checks["bipolars"].isChecked()
        if layer == "bad_contact_labels":
            return self.layer_checks["electrode_labels"].isChecked() and self.layer_checks["bad_contacts"].isChecked()
        if layer == "bad_bipolar_labels":
            return self.layer_checks["electrode_labels"].isChecked() and self.layer_checks["bad_bipolars"].isChecked()
        if layer == "shaft_labels":
            return self.layer_checks["shaft_labels"].isChecked() and self.layer_checks["shaft_lines"].isChecked()
        return self.layer_checks.get(layer).isChecked() if layer in self.layer_checks else True

    def remove_layer(self, layer: str) -> None:
        actors = self.actors.pop(layer, [])
        for actor in actors:
            try:
                self.plotter.remove_actor(actor, render=False)
            except Exception:
                pass

    def remove_dynamic_layers(self) -> None:
        for layer in list(DYNAMIC_LAYERS):
            self.remove_layer(layer)

    def on_layer_changed(self, layer: str) -> None:
        actors = self.actors.get(layer, [])
        if not actors:
            if layer == "surface":
                self.add_surface_layer()
            elif layer in DYNAMIC_LAYERS:
                self.refresh_data_layers()
            elif layer == "electrode_labels":
                self.refresh_data_layers()
            else:
                self.refresh_all()
            return
        visible = self.actor_layer_visible(layer)
        for actor in actors:
            if hasattr(actor, "SetVisibility"):
                actor.SetVisibility(bool(visible))
        self.update_dependent_label_visibility()
        self.plotter.render()

    def update_dependent_label_visibility(self) -> None:
        for layer in ["contact_labels", "bipolar_labels", "bad_contact_labels", "bad_bipolar_labels", "shaft_labels"]:
            visible = self.actor_layer_visible(layer)
            for actor in self.actors.get(layer, []):
                if hasattr(actor, "SetVisibility"):
                    actor.SetVisibility(bool(visible))

    def show_error(self, title: str, message: str) -> None:
        self.status_label.setText(f"{title}: {message}")
        QtWidgets.QMessageBox.warning(self, title, message)

    def show_status(self, message: str) -> None:
        self.status_label.setText(message)

    def current_camera_position(self) -> object | None:
        if not hasattr(self, "plotter"):
            return None
        try:
            return self.plotter.camera_position
        except Exception:
            return None

    def restore_camera_position(self, camera_position: object | None) -> None:
        if camera_position is None or not hasattr(self, "plotter"):
            return
        try:
            self.plotter.camera_position = camera_position
        except Exception:
            pass

    def selected_layers(self) -> set[str]:
        return {key for key, cb in self.layer_checks.items() if cb.isChecked()}

    def coordinate_mode(self) -> str:
        return "mni" if self.coord_combo.currentIndex() == 1 else "scs"

    def color_mode(self) -> str:
        return ["burn", "region", "shaft", "suspicion"][self.color_combo.currentIndex()]

    def region_source_mode(self) -> str:
        return "brainstorm" if self.region_source_combo.currentIndex() == 1 else "combined"

    def region_source_column(self) -> str:
        return "region_brainstorm" if self.region_source_mode() == "brainstorm" else "region_combined"

    def region_source_label(self) -> str:
        return "Brainstorm版本" if self.region_source_mode() == "brainstorm" else "结合版本"

    def selected_regions(self) -> list[str]:
        return [item.data(QtCore.Qt.UserRole) for item in self.region_list.selectedItems()]

    def selected_shafts(self) -> list[str]:
        return [item.text() for item in self.shaft_list.selectedItems()]

    def region_summary_for_patient(self, patient: str) -> pd.DataFrame:
        col = self.region_source_column()
        b = self.data.bipolars[self.data.bipolars["patient_id"].eq(patient)].copy()
        if b.empty or col not in b.columns:
            return pd.DataFrame(columns=["region", "n_bipolars", "n_doctor_burned_bipolars", "is_doctor_touched_region"])
        b["region_for_view"] = b[col].map(project_display_region)
        b = b[b["region_for_view"].astype(bool)].copy()
        if b.empty:
            return pd.DataFrame(columns=["region", "n_bipolars", "n_doctor_burned_bipolars", "is_doctor_touched_region"])
        out = (
            b.groupby("region_for_view", dropna=False)
            .agg(
                n_bipolars=("bipolar_channel", "size"),
                n_doctor_burned_bipolars=("is_doctor_burned", "sum"),
            )
            .reset_index()
            .rename(columns={"region_for_view": "region"})
        )
        out["n_doctor_burned_bipolars"] = out["n_doctor_burned_bipolars"].astype(int)
        out["is_doctor_touched_region"] = out["n_doctor_burned_bipolars"].gt(0)
        return out.sort_values(["is_doctor_touched_region", "n_doctor_burned_bipolars", "n_bipolars", "region"], ascending=[False, False, False, True])

    def populate_regions(self) -> None:
        patient = self.current_patient
        state = self.state_for(patient)
        mode = self.region_source_mode()
        if state.selected_regions_by_source is None:
            state.selected_regions_by_source = {}
        selected = set(state.selected_regions_by_source.get(mode, set()))
        text = self.region_filter.text().strip().lower()
        regs = self.region_summary_for_patient(patient)
        self.region_list.blockSignals(True)
        self.region_list.clear()
        for r in regs.itertuples():
            region = str(r.region)
            if not region or region == "nan":
                continue
            label = f"{region} ({int(r.n_doctor_burned_bipolars)}/{int(r.n_bipolars)})"
            if text and text not in label.lower():
                continue
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, region)
            item.setSelected(region in selected)
            self.region_list.addItem(item)
        self.region_list.blockSignals(False)

    def populate_shafts(self) -> None:
        patient = self.current_patient
        selected = set(self.state_for(patient).selected_shafts)
        shafts = sorted(self.data.bipolars.loc[self.data.bipolars["patient_id"].eq(patient), "shaft"].dropna().astype(str).unique())
        self.shaft_list.blockSignals(True)
        self.shaft_list.clear()
        for shaft in shafts:
            item = QtWidgets.QListWidgetItem(shaft)
            item.setSelected(shaft in selected)
            self.shaft_list.addItem(item)
        self.shaft_list.blockSignals(False)

    def clear_regions(self) -> None:
        self.region_list.clearSelection()
        self.save_patient_state(self.current_patient)
        self.refresh_data_layers()

    def coords_for(self, df: pd.DataFrame, kind: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        mode = self.coordinate_mode()
        if mode == "scs":
            if kind == "contact":
                return df["scs_x"].to_numpy(float), df["scs_y"].to_numpy(float), df["scs_z"].to_numpy(float)
            if kind == "region":
                return df["scs_x_centroid"].to_numpy(float), df["scs_y_centroid"].to_numpy(float), df["scs_z_centroid"].to_numpy(float)
            return df["brainstorm_scs_x"].to_numpy(float), df["brainstorm_scs_y"].to_numpy(float), df["brainstorm_scs_z"].to_numpy(float)
        if kind == "region":
            return df["x_centroid"].to_numpy(float), df["y_centroid"].to_numpy(float), df["z_centroid"].to_numpy(float)
        return df["mni_x"].to_numpy(float), df["mni_y"].to_numpy(float), df["mni_z"].to_numpy(float)

    def filtered_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        patient = self.current_patient
        b = self.data.bipolars[self.data.bipolars["patient_id"].eq(patient)].copy()
        c = self.data.contacts[self.data.contacts["patient_id"].eq(patient)].copy()
        regions = self.selected_regions()
        shafts = self.selected_shafts()
        selected_keys = parse_selection(self.selection_text.toPlainText())
        if regions and self.restrict_to_regions_check.isChecked():
            col = self.region_source_column()
            region_values = b[col].map(project_display_region) if col in b.columns else pd.Series("", index=b.index)
            if self.region_source_mode() == "combined":
                b = b[
                    region_values.isin(regions)
                    | b["region_bipolar"].map(project_display_region).isin(regions)
                ]
            else:
                b = b[region_values.isin(regions)]
        if shafts:
            b = b[b["shaft"].astype(str).isin(shafts)]
            c = c[c["shaft"].astype(str).isin(shafts)]
        if self.selected_only_check.isChecked() and selected_keys:
            b = b[
                b["bipolar_channel"].astype(str).str.upper().isin(selected_keys)
                | b["canonical_bipolar_key"].astype(str).str.upper().isin(selected_keys)
            ]
            c = c[c["contact_name"].astype(str).str.upper().isin(selected_keys)]
        return b, c

    def ensure_surface_loading(self, patient: str) -> bool:
        if patient in self.data.surface_cache:
            return True
        if patient in self.surface_threads:
            return False
        self._reset_camera_after_surface_load = self._reset_camera_next_refresh
        self.show_loading(patient)
        thread = QtCore.QThread(self)
        worker = SurfaceLoadWorker(self.data, patient)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self.on_surface_loaded)
        worker.failed.connect(self.on_surface_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda p=patient: self.surface_threads.pop(p, None))
        self.surface_threads[patient] = (thread, worker)
        thread.start()
        return False

    def show_loading(self, patient: str) -> None:
        self.show_status(f"正在后台加载 {patient} 的高分辨率脑表面...")
        if self.loading_dialog is not None:
            self.loading_dialog.close()
        self.loading_dialog = QtWidgets.QProgressDialog(f"正在加载 {patient} 高分辨率脑表面...", "", 0, 0, self)
        self.loading_dialog.setWindowTitle("加载脑表面")
        self.loading_dialog.setCancelButton(None)
        self.loading_dialog.setWindowModality(QtCore.Qt.NonModal)
        self.loading_dialog.setMinimumDuration(0)
        self.loading_dialog.show()

    def close_loading(self) -> None:
        if self.loading_dialog is not None:
            self.loading_dialog.close()
            self.loading_dialog = None

    def on_surface_loaded(self, patient: str, _bundle: object) -> None:
        if patient != self.current_patient:
            return
        self.close_loading()
        self.show_status(f"{patient} 高分辨率脑表面加载完成")
        self.add_surface_layer()
        self._reset_camera_after_surface_load = False
        self.plotter.render()

    def on_surface_failed(self, patient: str, message: str) -> None:
        if patient == self.current_patient:
            self.close_loading()
            self.show_error("脑表面加载失败", f"{patient}: {message}")

    def add_surface_layer(self) -> None:
        if self.coordinate_mode() != "scs":
            return
        if not self.layer_checks["surface"].isChecked() and "surface" not in self.actors:
            return
        if not self.layer_checks["surface"].isChecked() and "surface" in self.actors:
            return
        patient = self.current_patient
        if not self.ensure_surface_loading(patient):
            return
        camera_position = self.current_camera_position()
        self.remove_layer("surface")
        try:
            bundle = self.data.surface(patient)
            self.add_layer_actor("surface", self.plotter.add_mesh(
                bundle.cortex,
                color="#9aa6b7",
                opacity=0.18,
                smooth_shading=True,
                name="patient cortex",
                pickable=False,
            ))
            self.restore_camera_position(camera_position)
        except Exception as exc:
            self.show_error("脑表面显示失败", f"{patient}: {type(exc).__name__}: {exc}")

    def refresh_data_layers(self) -> None:
        if not hasattr(self, "plotter"):
            return
        try:
            camera_position = self.current_camera_position()
            self.save_patient_state(self.current_patient)
            self.remove_dynamic_layers()
            self.current_bipolars, self.current_contacts = self.filtered_data()
            self.add_data_layers()
            self.restore_camera_position(camera_position)
            self.update_stats()
            self.update_table()
            self.plotter.render()
        except Exception as exc:
            self.show_error("刷新显示失败", f"{type(exc).__name__}: {exc}")

    def refresh_manual_selection_layer(self) -> None:
        if not hasattr(self, "plotter"):
            return
        try:
            camera_position = self.current_camera_position()
            self.remove_layer("manual_selection")
            self.add_manual_selection()
            self.restore_camera_position(camera_position)
            self.plotter.render()
        except Exception as exc:
            self.show_error("手动选择失败", f"{type(exc).__name__}: {exc}")

    def refresh_all(self) -> None:
        if not hasattr(self, "plotter"):
            return
        try:
            camera_position = None
            state = self.state_for(self.current_patient)
            if state.camera_by_mode and self.coordinate_mode() in state.camera_by_mode:
                camera_position = state.camera_by_mode[self.coordinate_mode()]
            elif not self._reset_camera_next_refresh:
                try:
                    camera_position = self.plotter.camera_position
                except Exception:
                    camera_position = None
            self.plotter.clear()
            self.actors.clear()
            self.current_bipolars, self.current_contacts = self.filtered_data()
            self.add_surface_layer()
            self.add_data_layers()
            self.plotter.add_axes()
            if camera_position is None:
                self.plotter.reset_camera()
            else:
                self.plotter.camera_position = camera_position
            self._reset_camera_next_refresh = False
            self.update_stats()
            self.update_table()
        except Exception as exc:
            self.show_error("刷新显示失败", f"{type(exc).__name__}: {exc}")

    def add_data_layers(self) -> None:
        patient = self.current_patient
        b = self.current_bipolars
        c = self.current_contacts

        if self.coordinate_mode() == "scs" and self.selected_regions():
            self.add_selected_region_surfaces(patient)
        else:
            self.status_label.setText("")

        if not c.empty:
            shaft_label_points = []
            shaft_label_text = []
            for shaft, sub in c.sort_values(["shaft", "contact_index"]).groupby("shaft", sort=True):
                x, y, z = self.coords_for(sub, "contact")
                points = np.column_stack([x, y, z])
                if len(points) >= 2:
                    self.add_layer_actor(
                        "shaft_lines",
                        self.plotter.add_lines(points, color=(0.63, 0.68, 0.76), width=2, connected=True, name=f"shaft {shaft}"),
                    )
                    mid_i = len(points) // 2
                    shaft_label_points.append(points[mid_i])
                    shaft_label_text.append(str(shaft))
            if shaft_label_points:
                self.add_text_labels(
                    "shaft_labels",
                    np.asarray(shaft_label_points, dtype=float),
                    shaft_label_text,
                    font_size=13,
                    text_color="#111827",
                    shape_color="#ffffff",
                    name="shaft labels",
                )

        if not c.empty:
            x, y, z = self.coords_for(c, "contact")
            contact_points = np.column_stack([x, y, z])
            self.add_layer_actor("contacts", self.plotter.add_points(
                contact_points,
                color="#aeb7c8",
                point_size=7,
                render_points_as_spheres=True,
                name="contacts",
            ))
            self.add_text_labels(
                "contact_labels",
                contact_points,
                [clean_str(x) for x in c["contact_name"]],
                font_size=10,
                text_color="#334155",
                shape_color="#f8fafc",
                name="contact labels",
            )
            bad_contacts = c[c["is_bad_contact"]].copy() if "is_bad_contact" in c.columns else pd.DataFrame()
            if not bad_contacts.empty:
                x, y, z = self.coords_for(bad_contacts, "contact")
                bad_contact_points = np.column_stack([x, y, z])
                self.add_layer_actor("bad_contacts", self.plotter.add_points(
                    bad_contact_points,
                    color=BAD_CHANNEL_COLOR,
                    point_size=13,
                    render_points_as_spheres=True,
                    name="bad contacts",
                ))
                self.add_text_labels(
                    "bad_contact_labels",
                    bad_contact_points,
                    [clean_str(x) for x in bad_contacts["contact_name"]],
                    font_size=11,
                    text_color=BAD_CHANNEL_COLOR,
                    shape_color=BAD_CHANNEL_LABEL_BG,
                    name="bad contact labels",
                )

        if not b.empty:
            burned = b[b["is_doctor_burned"]].copy()
            base = b.copy()
            if not base.empty:
                self.add_bipolar_points(base)
                x, y, z = self.coords_for(base, "bipolar")
                base_points = np.column_stack([x, y, z])
                nonburn_mask = ~base["is_doctor_burned"].to_numpy(bool)
                if nonburn_mask.any():
                    self.add_text_labels(
                        "bipolar_labels",
                        base_points[nonburn_mask],
                        [clean_str(x) for x in base.loc[nonburn_mask, "bipolar_channel"]],
                        font_size=10,
                        text_color="#111827",
                        shape_color="#eef2ff",
                        name="bipolar labels",
                    )
                burn_mask = base["is_doctor_burned"].to_numpy(bool)
                if burn_mask.any():
                    self.add_text_labels(
                        "bipolar_labels",
                        base_points[burn_mask],
                        [clean_str(x) for x in base.loc[burn_mask, "bipolar_channel"]],
                        font_size=11,
                        text_color="#dc2626",
                        shape_color="#fee2e2",
                        name="burned bipolar labels",
                    )
            if not burned.empty:
                x, y, z = self.coords_for(burned, "bipolar")
                self.add_layer_actor("burned", self.plotter.add_points(
                    np.column_stack([x, y, z]),
                    color="#ff253a",
                    point_size=12,
                    render_points_as_spheres=True,
                    name="doctor burned",
                ))
            bad_bipolars = b[b["is_bad_bipolar"]].copy() if "is_bad_bipolar" in b.columns else pd.DataFrame()
            if not bad_bipolars.empty:
                x, y, z = self.coords_for(bad_bipolars, "bipolar")
                bad_bipolar_points = np.column_stack([x, y, z])
                self.add_layer_actor("bad_bipolars", self.plotter.add_points(
                    bad_bipolar_points,
                    color=BAD_CHANNEL_COLOR,
                    point_size=17,
                    render_points_as_spheres=True,
                    name="bad bipolars",
                ))
                self.add_text_labels(
                    "bad_bipolar_labels",
                    bad_bipolar_points,
                    [clean_str(x) for x in bad_bipolars["bipolar_channel"]],
                    font_size=12,
                    text_color=BAD_CHANNEL_COLOR,
                    shape_color=BAD_CHANNEL_LABEL_BG,
                    name="bad bipolar labels",
                )

        regs = self.region_centroids_for_patient(patient)
        selected_regions = self.selected_regions()
        if selected_regions and not regs.empty:
            regs = regs[regs["region"].astype(str).isin(selected_regions)]
        if not regs.empty:
            x, y, z = self.coords_for(regs, "region")
            self.add_layer_actor("region_centroids", self.plotter.add_points(
                np.column_stack([x, y, z]),
                color="#ff9b42",
                point_size=20,
                render_points_as_spheres=True,
                name="doctor touched DK regions",
            ))

        self.add_manual_selection()

    def region_centroids_for_patient(self, patient: str) -> pd.DataFrame:
        col = self.region_source_column()
        b = self.data.bipolars[self.data.bipolars["patient_id"].eq(patient)].copy()
        if b.empty or col not in b.columns:
            return pd.DataFrame()
        b["region"] = b[col].map(project_display_region)
        b = b[b["region"].astype(bool)].copy()
        if b.empty:
            return pd.DataFrame()
        x, y, z = self.coords_for(b, "bipolar")
        b["_x"] = x
        b["_y"] = y
        b["_z"] = z
        out = (
            b.groupby("region", dropna=False)
            .agg(
                n_doctor_burned_bipolars=("is_doctor_burned", "sum"),
                _x=("_x", "mean"),
                _y=("_y", "mean"),
                _z=("_z", "mean"),
            )
            .reset_index()
        )
        out = out[out["n_doctor_burned_bipolars"].astype(int).gt(0)].copy()
        if self.coordinate_mode() == "scs":
            out["scs_x_centroid"] = out["_x"]
            out["scs_y_centroid"] = out["_y"]
            out["scs_z_centroid"] = out["_z"]
        else:
            out["x_centroid"] = out["_x"]
            out["y_centroid"] = out["_y"]
            out["z_centroid"] = out["_z"]
        return out

    def add_text_labels(
        self,
        layer: str,
        points: np.ndarray,
        labels: list[str],
        font_size: int,
        text_color: str,
        shape_color: str,
        name: str,
    ) -> None:
        if points.size == 0 or not labels:
            return
        camera_position = self.current_camera_position()
        actor = self.plotter.add_point_labels(
            points,
            labels,
            show_points=False,
            always_visible=True,
            font_size=font_size,
            text_color=text_color,
            shape_color=shape_color,
            shape_opacity=0.72,
            margin=2,
            name=name,
            reset_camera=False,
            render=False,
        )
        self.add_layer_actor(layer, actor)
        self.restore_camera_position(camera_position)

    def bipolar_colors(self, b: pd.DataFrame):
        mode = self.color_mode()
        if mode == "region":
            col = self.region_source_column()
            regions = b[col].map(project_display_region) if col in b.columns else pd.Series("", index=b.index)
            vals = sorted(str(x) for x in regions.fillna("").unique())
            cmap = {v: COLORWAY[i % len(COLORWAY)] for i, v in enumerate(vals)}
            return [cmap.get(str(x), "#6f7787") for x in regions.fillna("")]
        if mode == "shaft":
            vals = sorted(str(x) for x in b["shaft"].fillna("").unique())
            cmap = {v: COLORWAY[i % len(COLORWAY)] for i, v in enumerate(vals)}
            return [cmap.get(str(x), "#6f7787") for x in b["shaft"].fillna("")]
        if mode == "suspicion" and "suspicion_percentile" in b.columns:
            return pd.to_numeric(b["suspicion_percentile"], errors="coerce").fillna(0.0).to_numpy(float)
        return ["#6f7787" for _ in range(len(b))]

    def add_bipolar_points(self, b: pd.DataFrame) -> None:
        x, y, z = self.coords_for(b, "bipolar")
        points = np.column_stack([x, y, z])
        colors = self.bipolar_colors(b)
        if isinstance(colors, np.ndarray) and colors.ndim == 1:
            self.add_layer_actor("bipolars", self.plotter.add_points(
                points,
                scalars=colors,
                cmap="viridis",
                clim=[0, 1],
                point_size=9,
                render_points_as_spheres=True,
                name="bipolar midpoints",
            ))
            return
        color_array = np.asarray(colors, dtype=object)
        for color in pd.unique(color_array):
            mask = color_array == color
            if mask.any():
                self.add_layer_actor("bipolars", self.plotter.add_points(
                    points[mask],
                    color=str(color),
                    point_size=9,
                    render_points_as_spheres=True,
                    name=f"bipolar midpoints {color}",
                ))

    def add_selected_region_surfaces(self, patient: str) -> None:
        bundle = self.data.surface(patient)
        shown = []
        missing = []
        for region in self.selected_regions():
            for part in str(region).split("|"):
                key = normalize_dk_surface_label(part)
                scout = bundle.dk_scouts_by_norm.get(key)
                source = "DK"
                vertices = bundle.cortex_vertices
                faces = bundle.cortex_faces
                if scout is None:
                    scout = bundle.aseg_scouts_by_norm.get(key)
                    source = "ASEG"
                    vertices = bundle.aseg_vertices
                    faces = bundle.aseg_faces
                if scout is None or vertices.size == 0 or faces.size == 0:
                    missing.append(str(part))
                    continue
                mesh = self.region_mesh(vertices, faces, np.asarray(scout["vertices"], dtype=np.int32))
                if mesh is None:
                    missing.append(str(part))
                    continue
                self.add_layer_actor("selected_regions", self.plotter.add_mesh(
                    mesh,
                    color=rgb_float_to_hex(scout["color"]),
                    opacity=0.82 if source == "DK" else 0.92,
                    smooth_shading=True,
                    name=f"selected {source}: {scout['label']}",
                    pickable=False,
                ))
                shown.append(f"{source}:{scout['label']}")
        pieces = []
        if shown:
            pieces.append(f"{self.region_source_label()}高亮脑区：" + "；".join(shown))
        if missing:
            pieces.append("未找到可显示脑区面：" + "；".join(dict.fromkeys(missing)))
        self.status_label.setText("\n".join(pieces))

    @staticmethod
    def region_mesh(vertices: np.ndarray, faces: np.ndarray, scout_vertices: np.ndarray) -> pv.PolyData | None:
        if scout_vertices.size == 0:
            return None
        scout_vertices = scout_vertices[(scout_vertices >= 0) & (scout_vertices < vertices.shape[0])]
        if scout_vertices.size == 0:
            return None
        mask = np.zeros(vertices.shape[0], dtype=bool)
        mask[scout_vertices] = True
        face_mask = mask[faces].all(axis=1)
        if not face_mask.any():
            face_mask = mask[faces].sum(axis=1) >= 2
        region_faces = faces[face_mask]
        if region_faces.size == 0:
            return None
        used = np.unique(region_faces.ravel())
        remap = np.full(vertices.shape[0], -1, dtype=np.int32)
        remap[used] = np.arange(used.size, dtype=np.int32)
        return make_polydata(vertices[used], remap[region_faces])

    def add_manual_selection(self) -> None:
        keys = parse_selection(self.selection_text.toPlainText())
        if not keys:
            return
        b = self.data.bipolars[
            self.data.bipolars["patient_id"].eq(self.current_patient)
            & (
                self.data.bipolars["bipolar_channel"].astype(str).str.upper().isin(keys)
                | self.data.bipolars["canonical_bipolar_key"].astype(str).str.upper().isin(keys)
            )
        ]
        c = self.data.contacts[
            self.data.contacts["patient_id"].eq(self.current_patient)
            & self.data.contacts["contact_name"].astype(str).str.upper().isin(keys)
        ]
        if not b.empty:
            x, y, z = self.coords_for(b, "bipolar")
            self.add_layer_actor("manual_selection", self.plotter.add_points(
                np.column_stack([x, y, z]),
                color="#ffd400",
                point_size=18,
                render_points_as_spheres=True,
                name="selected bipolars",
            ))
        if not c.empty:
            x, y, z = self.coords_for(c, "contact")
            self.add_layer_actor("manual_selection", self.plotter.add_points(
                np.column_stack([x, y, z]),
                color="#fff176",
                point_size=14,
                render_points_as_spheres=True,
                name="selected contacts",
            ))

    def on_3d_point_picked(self, point: object) -> None:
        if point is None:
            return
        try:
            picked = np.asarray(point, dtype=float).ravel()[:3]
            if picked.size != 3 or np.isnan(picked).any():
                return
            hit = self.nearest_displayed_item(picked)
            if hit is None:
                self.detail_label.setText("未匹配到附近的电极点；请靠近双极中点或单接触点点击。")
                return
            kind, row, coord, distance = hit
            self.highlight_picked_point(coord)
            if kind == "bipolar":
                self.show_bipolar_detail(row, prefix=f"3D 点选，距离 {distance:.2f} mm")
                self.select_table_channel(clean_str(row.get("bipolar_channel", "")))
            else:
                self.show_contact_detail(row, prefix=f"3D 点选，距离 {distance:.2f} mm")
        except Exception as exc:
            self.show_error("3D 点选失败", f"{type(exc).__name__}: {exc}")

    def on_3d_right_click(self, click_position: object = None, *_args: object) -> None:
        try:
            hit = self.nearest_displayed_item_by_screen(click_position)
            if hit is None:
                try:
                    picked = np.asarray(self.plotter.pick_click_position(), dtype=float).ravel()[:3]
                    if picked.size == 3 and np.isfinite(picked).all():
                        hit = self.nearest_displayed_item(picked)
                except Exception:
                    pass
        except Exception as exc:
            self.show_error("3D 点选失败", f"{type(exc).__name__}: {exc}")
            return
        self.apply_pick_hit(hit)

    def on_3d_qt_right_click(self, qt_position: np.ndarray) -> None:
        try:
            hit = self.nearest_displayed_item_by_qt_position(qt_position)
        except Exception as exc:
            self.show_error("3D 点选失败", f"{type(exc).__name__}: {exc}")
            return
        self.apply_pick_hit(hit)

    def nearest_displayed_item(self, picked: np.ndarray) -> tuple[str, pd.Series, np.ndarray, float] | None:
        candidates: list[tuple[str, pd.Series, np.ndarray, float]] = []
        if not self.current_bipolars.empty:
            x, y, z = self.coords_for(self.current_bipolars, "bipolar")
            coords = np.column_stack([x, y, z])
            valid = np.isfinite(coords).all(axis=1)
            if valid.any():
                distances = np.linalg.norm(coords[valid] - picked, axis=1)
                local_i = int(np.argmin(distances))
                global_i = np.flatnonzero(valid)[local_i]
                candidates.append(("bipolar", self.current_bipolars.iloc[global_i], coords[global_i], float(distances[local_i])))
        if not self.current_contacts.empty:
            x, y, z = self.coords_for(self.current_contacts, "contact")
            coords = np.column_stack([x, y, z])
            valid = np.isfinite(coords).all(axis=1)
            if valid.any():
                distances = np.linalg.norm(coords[valid] - picked, axis=1)
                local_i = int(np.argmin(distances))
                global_i = np.flatnonzero(valid)[local_i]
                candidates.append(("contact", self.current_contacts.iloc[global_i], coords[global_i], float(distances[local_i])))
        if not candidates:
            return None
        hit = min(candidates, key=lambda item: item[3])
        threshold = 10.0 if self.coordinate_mode() == "scs" else 12.0
        return hit if hit[3] <= threshold else None

    def nearest_displayed_item_by_qt_position(self, qt_position: np.ndarray) -> tuple[str, pd.Series, np.ndarray, float] | None:
        click = np.asarray(qt_position, dtype=float).ravel()[:2]
        if click.size != 2 or np.isnan(click).any():
            return None
        click_variants = self.qt_click_position_variants(click)
        return self.nearest_displayed_item_from_click_variants(click_variants, threshold_px=72.0)

    def nearest_displayed_item_by_screen(self, click_position: object) -> tuple[str, pd.Series, np.ndarray, float] | None:
        if click_position is None:
            click_position = getattr(self.plotter, "click_position", None)
        if click_position is None:
            return None
        click = np.asarray(click_position, dtype=float).ravel()[:2]
        if click.size != 2 or np.isnan(click).any():
            return None
        click_variants = self.click_position_variants(click)
        return self.nearest_displayed_item_from_click_variants(click_variants, threshold_px=72.0)

    def nearest_displayed_item_from_click_variants(
        self,
        click_variants: list[np.ndarray],
        threshold_px: float,
    ) -> tuple[str, pd.Series, np.ndarray, float] | None:
        candidates: list[tuple[str, pd.Series, np.ndarray, float]] = []
        if not self.current_bipolars.empty and (
            self.layer_checks["bipolars"].isChecked()
            or self.layer_checks["burned"].isChecked()
            or self.layer_checks["bad_bipolars"].isChecked()
        ):
            b = self.current_bipolars
            if not self.layer_checks["bipolars"].isChecked():
                masks = []
                if self.layer_checks["burned"].isChecked():
                    masks.append(b["is_doctor_burned"].astype(bool))
                if self.layer_checks["bad_bipolars"].isChecked() and "is_bad_bipolar" in b.columns:
                    masks.append(b["is_bad_bipolar"].astype(bool))
                if masks:
                    mask = masks[0].copy()
                    for extra in masks[1:]:
                        mask = mask | extra
                    b = b[mask].copy()
            x, y, z = self.coords_for(b, "bipolar")
            coords = np.column_stack([x, y, z])
            self.append_screen_candidates(candidates, "bipolar", b, coords, click_variants)
        if not self.current_contacts.empty and (self.layer_checks["contacts"].isChecked() or self.layer_checks["bad_contacts"].isChecked()):
            c = self.current_contacts
            if not self.layer_checks["contacts"].isChecked() and self.layer_checks["bad_contacts"].isChecked() and "is_bad_contact" in c.columns:
                c = c[c["is_bad_contact"]].copy()
            x, y, z = self.coords_for(c, "contact")
            coords = np.column_stack([x, y, z])
            self.append_screen_candidates(candidates, "contact", c, coords, click_variants)
        if not candidates:
            return None
        hit = min(candidates, key=lambda item: item[3])
        self._last_pick_distance_px = hit[3]
        return hit if hit[3] <= threshold_px else None

    def qt_click_position_variants(self, click: np.ndarray) -> list[np.ndarray]:
        render_w, render_h = self.render_window_size()
        widget_w, widget_h = self.widget_size()
        x, y = float(click[0]), float(click[1])
        sx = render_w / widget_w if widget_w > 0 else 1.0
        sy = render_h / widget_h if widget_h > 0 else 1.0
        variants: list[np.ndarray] = []

        def add_variant(px: float, py: float) -> None:
            p = np.array([px, py], dtype=float)
            if np.isfinite(p).all() and not any(np.linalg.norm(p - old) < 0.5 for old in variants):
                variants.append(p)

        # Qt mouse positions are widget-local, top-left origin. VTK display
        # coordinates are render-window-local, bottom-left origin.
        add_variant(x * sx, render_h - y * sy)
        # Keep fallbacks for unusual OpenGL/Qt high-DPI combinations.
        add_variant(x * sx, y * sy)
        add_variant(x, render_h - y)
        add_variant(x, y)
        return variants

    def click_position_variants(self, click: np.ndarray) -> list[np.ndarray]:
        render_w, render_h = self.render_window_size()
        widget_w, widget_h = self.widget_size()
        variants: list[np.ndarray] = []

        def add_variant(x: float, y: float) -> None:
            if np.isfinite(x) and np.isfinite(y):
                p = np.array([x, y], dtype=float)
                if not any(np.linalg.norm(p - old) < 0.5 for old in variants):
                    variants.append(p)

        x, y = float(click[0]), float(click[1])
        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
            add_variant(x * render_w, y * render_h)
            add_variant(x * render_w, (1.0 - y) * render_h)
            return variants

        add_variant(x, y)
        add_variant(x, render_h - y)
        if widget_w > 0 and widget_h > 0:
            sx = render_w / widget_w if render_w > 0 else 1.0
            sy = render_h / widget_h if render_h > 0 else 1.0
            add_variant(x * sx, y * sy)
            add_variant(x * sx, render_h - y * sy)
        return variants

    def render_window_size(self) -> tuple[float, float]:
        try:
            w, h = self.plotter.ren_win.GetSize()
            return float(max(w, 1)), float(max(h, 1))
        except Exception:
            return 1.0, 1.0

    def widget_size(self) -> tuple[float, float]:
        try:
            return float(max(self.plotter.interactor.width(), 1)), float(max(self.plotter.interactor.height(), 1))
        except Exception:
            return 1.0, 1.0

    def append_screen_candidates(
        self,
        candidates: list[tuple[str, pd.Series, np.ndarray, float]],
        kind: str,
        df: pd.DataFrame,
        coords: np.ndarray,
        click_variants: list[np.ndarray],
    ) -> None:
        valid = np.isfinite(coords).all(axis=1)
        if not valid.any():
            return
        screen_points = []
        rows = []
        world_coords = []
        for row_i, coord in zip(np.flatnonzero(valid), coords[valid]):
            screen = self.world_to_display(coord)
            if screen is None:
                continue
            screen_points.append(screen)
            rows.append(row_i)
            world_coords.append(coord)
        if not screen_points:
            return
        screen_arr = np.asarray(screen_points, dtype=float)
        best_distance = None
        best_local_i = None
        for click in click_variants:
            distances = np.linalg.norm(screen_arr - click.reshape(1, 2), axis=1)
            local_i = int(np.argmin(distances))
            distance = float(distances[local_i])
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_local_i = local_i
        if best_local_i is not None and best_distance is not None:
            candidates.append((kind, df.iloc[rows[best_local_i]], np.asarray(world_coords[best_local_i], dtype=float), float(best_distance)))

    def world_to_display(self, coord: np.ndarray) -> np.ndarray | None:
        try:
            renderer = self.plotter.renderer
            renderer.SetWorldPoint(float(coord[0]), float(coord[1]), float(coord[2]), 1.0)
            renderer.WorldToDisplay()
            x, y, _z = renderer.GetDisplayPoint()
            return np.array([x, y], dtype=float)
        except Exception:
            return None

    def pick_key_for(self, kind: str, row: pd.Series) -> tuple[str, str]:
        if kind == "bipolar":
            return kind, clean_str(row.get("bipolar_channel", ""))
        return kind, clean_str(row.get("contact_name", ""))

    def clear_pick_selection(self) -> None:
        self.selected_pick_key = None
        self.remove_layer("pick_highlight")
        self.detail_label.setText("点击/选择电极后在这里查看明细")
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.blockSignals(False)
        self.plotter.render()

    def apply_pick_hit(self, hit: tuple[str, pd.Series, np.ndarray, float] | None) -> None:
        if hit is None:
            distance = getattr(self, "_last_pick_distance_px", None)
            suffix = f" 最近电极投影距离约 {distance:.1f} px。" if distance is not None else ""
            self.detail_label.setText(f"未匹配到附近的电极点；请靠近屏幕中可见的双极中点或单接触点右键。{suffix}")
            return
        kind, row, coord, distance = hit
        pick_key = self.pick_key_for(kind, row)
        if self.selected_pick_key == pick_key:
            self.clear_pick_selection()
            return
        self.selected_pick_key = pick_key
        self.highlight_picked_point(coord)
        if kind == "bipolar":
            self.show_bipolar_detail(row, prefix=f"3D 右键点选，屏幕距离 {distance:.1f} px")
            self.select_table_channel(clean_str(row.get("bipolar_channel", "")))
        else:
            self.show_contact_detail(row, prefix=f"3D 右键点选，屏幕距离 {distance:.1f} px")

    def highlight_picked_point(self, coord: np.ndarray) -> None:
        camera_position = self.current_camera_position()
        self.remove_layer("pick_highlight")
        self.add_layer_actor("pick_highlight", self.plotter.add_points(
            np.asarray(coord, dtype=float).reshape(1, 3),
            color="#ffd400",
            point_size=24,
            render_points_as_spheres=True,
            name="picked electrode",
        ))
        self.restore_camera_position(camera_position)
        self.plotter.render()

    def show_bipolar_detail(self, r: pd.Series, prefix: str = "") -> None:
        lead = f"{prefix} | " if prefix else ""
        self.detail_label.setText(
            f"{lead}{r['bipolar_channel']} | shaft={r['shaft']} | DK={r['region_bipolar']} | projected={clean_str(r.get('region_projected', ''))} | "
            f"Brainstorm={clean_str(r.get('dk_region_from_brainstorm_bipolar', ''))} | "
            f"医生烧毁={'是' if bool(r.get('is_doctor_burned', False)) else '否'} | "
            f"坏导={'是' if bool(r.get('is_bad_bipolar', False)) else '否'} | "
            f"SCS=({r['brainstorm_scs_x']:.2f}, {r['brainstorm_scs_y']:.2f}, {r['brainstorm_scs_z']:.2f}) | "
            f"MNI=({r['mni_x']:.2f}, {r['mni_y']:.2f}, {r['mni_z']:.2f})"
        )

    def show_contact_detail(self, r: pd.Series, prefix: str = "") -> None:
        lead = f"{prefix} | " if prefix else ""
        region = clean_str(r.get("dk_region", r.get("region", r.get("region_projected", ""))))
        self.detail_label.setText(
            f"{lead}{r['contact_name']} | shaft={clean_str(r.get('shaft', ''))} | DK={region} | "
            f"坏导={'是' if bool(r.get('is_bad_contact', False)) else '否'} | "
            f"SCS=({r['scs_x']:.2f}, {r['scs_y']:.2f}, {r['scs_z']:.2f}) | "
            f"MNI=({r['mni_x']:.2f}, {r['mni_y']:.2f}, {r['mni_z']:.2f})"
        )

    def select_table_channel(self, channel: str) -> None:
        if not channel:
            return
        self.table.blockSignals(True)
        self.table.clearSelection()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(QtCore.Qt.UserRole) == channel:
                self.table.selectRow(row)
                self.table.scrollToItem(item)
                break
        self.table.blockSignals(False)

    def update_stats(self) -> None:
        s = self.data.summary[self.data.summary["patient_id"].eq(self.current_patient)].iloc[0]
        a = self.data.audit[self.data.audit["patient_id"].eq(self.current_patient)].iloc[0]
        self.stats_label.setText(
            f"患者 {self.current_patient} | 接触点 {int(s['n_contacts'])} | 双极 {int(s['n_bipolars'])} | "
            f"医生烧毁双极 {int(s['n_doctor_burned_bipolars'])} | 烧毁触及 DK 脑区 {int(s['n_touched_projected_regions'])} | "
            f"医生主要脑区 {clean_str(s['top_doctor_region'])} | 高分辨率皮层 {int(a.get('n_high_source_vertices', 0))} 顶点 / {int(a.get('n_high_source_faces', 0))} 面片"
        )

    def update_table(self) -> None:
        cols = [
            "bipolar_channel",
            "shaft",
            "region_bipolar",
            "region_projected",
            "dk_region_from_brainstorm_bipolar",
            "is_doctor_burned",
            "is_bad_bipolar",
            "bad_bipolar_labels",
            "suspicion_rank",
            "suspicion_percentile",
        ]
        df = self.current_bipolars[[c for c in cols if c in self.current_bipolars.columns]].copy()
        df = df.sort_values(["is_doctor_burned", "shaft", "bipolar_channel"], ascending=[False, True, True]).head(500)
        self.table.setColumnCount(len(df.columns))
        self.table.setRowCount(len(df))
        self.table.setHorizontalHeaderLabels(df.columns.tolist())
        for row_i, (_, row) in enumerate(df.iterrows()):
            for col_i, col in enumerate(df.columns):
                val = row[col]
                if col == "suspicion_percentile" and not pd.isna(val):
                    text = f"{float(val):.3f}"
                else:
                    text = clean_str(val)
                item = QtWidgets.QTableWidgetItem(text)
                item.setData(QtCore.Qt.UserRole, clean_str(row.get("bipolar_channel", "")))
                self.table.setItem(row_i, col_i, item)
        self.table.resizeColumnsToContents()

    def on_table_selection(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        channel = self.table.item(row, 0).data(QtCore.Qt.UserRole)
        b = self.data.bipolars[
            self.data.bipolars["patient_id"].eq(self.current_patient)
            & self.data.bipolars["bipolar_channel"].astype(str).eq(str(channel))
        ]
        if b.empty:
            return
        r = b.iloc[0]
        self.show_bipolar_detail(r)
        x, y, z = self.coords_for(b, "bipolar")
        self.highlight_picked_point(np.array([x[0], y[0], z[0]], dtype=float))


def main() -> None:
    pv.global_theme.multi_samples = 8
    parser = argparse.ArgumentParser(description="Patient electrode desktop viewer")
    parser.add_argument("--data-dir", type=Path, help="viewer_data directory prepared by the user")
    parser.add_argument("--bad-channels", type=Path, help="optional bad-channel Excel file")
    args, qt_args = parser.parse_known_args()
    if hasattr(QtCore.Qt, "AA_EnableHighDpiScaling"):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, "AA_UseHighDpiPixmaps"):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication([sys.argv[0], *qt_args])
    screen = app.primaryScreen()
    scale = 1.0
    if screen is not None:
        scale = max(1.0, screen.logicalDotsPerInch() / 96.0)
    font = app.font()
    font.setFamily("Microsoft YaHei")
    font.setPointSizeF(min(14.0, max(10.5, 10.5 * scale)))
    app.setFont(font)
    try:
        data_dir = args.data_dir or configured_data_dir()
        bad_channels_path = args.bad_channels or configured_bad_channels_path()
        while data_dir is None:
            selected = QtWidgets.QFileDialog.getExistingDirectory(None, "选择 viewer_data 数据目录")
            if not selected:
                QtWidgets.QMessageBox.information(None, APP_TITLE, "未选择数据目录，程序将退出。")
                return
            data_dir = Path(selected)
        data_dir = validate_data_dir(data_dir)
        write_config(data_dir, bad_channels_path)
        viewer = DesktopViewer(data_dir, bad_channels_path)
    except Exception as exc:
        QtWidgets.QMessageBox.critical(None, "患者电极查看器启动失败", f"{type(exc).__name__}: {exc}")
        raise
    viewer.show()
    sys.exit(app.exec_() if hasattr(app, "exec_") else app.exec())


if __name__ == "__main__":
    main()
