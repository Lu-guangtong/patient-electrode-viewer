# -*- coding: utf-8 -*-
"""Generate synthetic sample data for the public patient electrode viewer."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np


OUT = Path(__file__).resolve().parents[1] / "sample_data"
PATIENT = "sample01"


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def make_surface() -> None:
    surface_dir = OUT / "surfaces"
    surface_dir.mkdir(parents=True, exist_ok=True)

    theta = np.linspace(0.0, np.pi, 18)
    phi = np.linspace(0.0, 2.0 * np.pi, 36, endpoint=False)
    vertices = []
    for t in theta:
        for p in phi:
            vertices.append([42.0 * np.sin(t) * np.cos(p), 35.0 * np.sin(t) * np.sin(p), 48.0 * np.cos(t)])
    vertices_arr = np.asarray(vertices, dtype=np.float32)

    faces = []
    n_phi = len(phi)
    for i in range(len(theta) - 1):
        for j in range(n_phi):
            a = i * n_phi + j
            b = i * n_phi + ((j + 1) % n_phi)
            c = (i + 1) * n_phi + j
            d = (i + 1) * n_phi + ((j + 1) % n_phi)
            faces.append([a, c, b])
            faces.append([b, c, d])
    faces_arr = np.asarray(faces, dtype=np.int32)

    np.savez(
        surface_dir / f"{PATIENT}_cortex_pial_high.npz",
        vertices_scs_mm=vertices_arr,
        faces=faces_arr,
        source_path="synthetic sample",
        source_vertices=vertices_arr.shape[0],
        source_faces=faces_arr.shape[0],
        display_target_faces=faces_arr.shape[0],
    )

    left_vertices = np.flatnonzero(vertices_arr[:, 0] < 0).astype(int).tolist()
    right_vertices = np.flatnonzero(vertices_arr[:, 0] >= 0).astype(int).tolist()
    scouts = [
        {
            "label": "Synthetic temporal L",
            "normalized_label": "synthetic temporal l",
            "vertices": left_vertices,
            "color": [0.2, 0.55, 0.9],
            "n_vertices": len(left_vertices),
        },
        {
            "label": "Synthetic temporal R",
            "normalized_label": "synthetic temporal r",
            "vertices": right_vertices,
            "color": [0.95, 0.55, 0.2],
            "n_vertices": len(right_vertices),
        },
    ]
    (surface_dir / f"{PATIENT}_desikan_killiany_scouts.json").write_text(
        json.dumps(scouts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    contacts = []
    for idx in range(1, 7):
        x = -18.0 + idx * 6.0
        y = -12.0 + idx * 2.5
        z = 8.0 + idx
        contacts.append(
            {
                "patient_id": PATIENT,
                "contact_name": f"A{idx}",
                "contact_norm": f"A{idx}",
                "shaft": "A",
                "contact_index": idx,
                "mni_x": x + 1.5,
                "mni_y": y - 2.0,
                "mni_z": z + 0.5,
                "scs_x": x,
                "scs_y": y,
                "scs_z": z,
                "world_x": x,
                "world_y": y,
                "world_z": z,
                "dk_region": "Synthetic temporal L" if idx <= 3 else "Synthetic temporal R",
                "dk_region_prob": "1.0",
                "source_file": "synthetic",
                "x": x + 1.5,
                "y": y - 2.0,
                "z": z + 0.5,
                "coordinate_space": "MNI and SCS",
                "is_coordinate_valid": True,
            }
        )

    bipolars = []
    for idx in range(1, 6):
        a = contacts[idx - 1]
        c = contacts[idx]
        region = a["dk_region"] if idx <= 2 else c["dk_region"]
        scs_x = (float(a["scs_x"]) + float(c["scs_x"])) / 2.0
        scs_y = (float(a["scs_y"]) + float(c["scs_y"])) / 2.0
        scs_z = (float(a["scs_z"]) + float(c["scs_z"])) / 2.0
        mni_x = (float(a["mni_x"]) + float(c["mni_x"])) / 2.0
        mni_y = (float(a["mni_y"]) + float(c["mni_y"])) / 2.0
        mni_z = (float(a["mni_z"]) + float(c["mni_z"])) / 2.0
        bipolars.append(
            {
                "patient_id": PATIENT,
                "canonical_bipolar_key": f"A{idx}-A{idx + 1}",
                "bipolar_channel": f"A{idx}-A{idx + 1}",
                "anode": f"A{idx}",
                "cathode": f"A{idx + 1}",
                "shaft": "A",
                "contact_index_anode": idx,
                "contact_index_cathode": idx + 1,
                "x_mid": mni_x,
                "y_mid": mni_y,
                "z_mid": mni_z,
                "contact_distance_mm": 6.6,
                "region_anode": a["dk_region"],
                "region_cathode": c["dk_region"],
                "region_bipolar": region,
                "region_projected": region,
                "hemisphere_bipolar": "L" if " L" in region else "R",
                "same_region": a["dk_region"] == c["dk_region"],
                "brainstorm_mni_x": mni_x,
                "brainstorm_mni_y": mni_y,
                "brainstorm_mni_z": mni_z,
                "brainstorm_scs_x": scs_x,
                "brainstorm_scs_y": scs_y,
                "brainstorm_scs_z": scs_z,
                "brainstorm_world_x": scs_x,
                "brainstorm_world_y": scs_y,
                "brainstorm_world_z": scs_z,
                "dk_region_from_brainstorm_bipolar": region,
                "dk_region_prob": "1.0",
                "source_file": "synthetic",
                "mni_x": mni_x,
                "mni_y": mni_y,
                "mni_z": mni_z,
                "x": mni_x,
                "y": mni_y,
                "z": mni_z,
                "delta_master_vs_brainstorm_x": 0.0,
                "delta_master_vs_brainstorm_y": 0.0,
                "delta_master_vs_brainstorm_z": 0.0,
                "max_abs_delta_master_vs_brainstorm_mni": 0.0,
                "doctor_burned_count": 1 if idx in {2, 4} else 0,
                "doctor_burned_source_electrodes": "synthetic" if idx in {2, 4} else "",
                "doctor_region_projected": region if idx in {2, 4} else "",
                "is_doctor_burned": idx in {2, 4},
                "method": "synthetic",
                "suspicion_score": round(0.15 * idx, 3),
                "suspicion_rank": idx,
                "suspicion_percentile": round(idx / 5.0, 3),
                "doctor_burned_bipolar_count": 1 if idx in {2, 4} else 0,
                "label_top1": region,
                "label_top2": region,
                "label_top70": region,
                "is_coordinate_valid": True,
                "display_label": f"A{idx}-A{idx + 1}",
            }
        )

    regions = [
        {
            "patient_id": PATIENT,
            "region_projected": "Synthetic temporal L",
            "n_bipolars": 2,
            "n_doctor_burned_bipolars": 1,
            "x_centroid": -6.5,
            "y_centroid": -12.0,
            "z_centroid": 11.0,
            "scs_x_centroid": -8.0,
            "scs_y_centroid": -10.0,
            "scs_z_centroid": 10.5,
            "shafts": "A",
            "is_doctor_touched_region": True,
        },
        {
            "patient_id": PATIENT,
            "region_projected": "Synthetic temporal R",
            "n_bipolars": 3,
            "n_doctor_burned_bipolars": 1,
            "x_centroid": 9.0,
            "y_centroid": -5.0,
            "z_centroid": 14.0,
            "scs_x_centroid": 7.5,
            "scs_y_centroid": -3.0,
            "scs_z_centroid": 13.5,
            "shafts": "A",
            "is_doctor_touched_region": True,
        },
    ]

    summary = [
        {
            "patient_id": PATIENT,
            "n_contacts": len(contacts),
            "n_bipolars": len(bipolars),
            "n_shafts": 1,
            "n_doctor_burned_bipolars": 2,
            "n_touched_projected_regions": 2,
            "top_doctor_region": "Synthetic temporal L",
            "top_doctor_region_burned_count": 1,
            "coordinate_space": "MNI and synthetic SCS",
            "has_patient_surface_model": True,
            "surface_model_note": "Synthetic sample surface for installation testing only.",
        }
    ]

    audit = [
        {
            "patient_id": PATIENT,
            "contacts": len(contacts),
            "contacts_missing_mni": 0,
            "bipolars": len(bipolars),
            "bipolars_missing_mni": 0,
            "doctor_raw_rows": 2,
            "doctor_detail_rows": 2,
            "doctor_matched_rows": 2,
            "viewer_burned_bipolars": 2,
            "doctor_unmatched_rows": 0,
            "max_abs_delta_master_vs_brainstorm_mni": 0.0,
            "has_patient_surface_model": True,
            "n_projected_regions": 2,
            "n_doctor_touched_regions": 2,
            "surface_found": True,
            "n_vertices": 648,
            "n_faces": 1224,
            "surface_path": "synthetic",
            "high_surface_found": True,
            "n_high_vertices": 648,
            "n_high_faces": 1224,
            "n_high_source_vertices": 648,
            "n_high_source_faces": 1224,
            "high_surface_path": "synthetic",
        }
    ]

    write_csv(OUT / "viewer_contacts.csv", contacts)
    write_csv(OUT / "viewer_bipolars.csv", bipolars)
    write_csv(OUT / "viewer_regions.csv", regions)
    write_csv(OUT / "viewer_patient_summary.csv", summary)
    write_csv(OUT / "viewer_data_audit.csv", audit)
    make_surface()


if __name__ == "__main__":
    main()
