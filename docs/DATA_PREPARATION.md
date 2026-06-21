# Data Preparation

This application does not ship real clinical data. Users must prepare a local, de-identified `viewer_data` folder and select it when the app starts.

Do not publish real patient coordinates, individual anatomy, Brainstorm databases, surgical labels, bad-channel tables, or raw clinical files in a public GitHub repository.

## Directory Layout

```text
viewer_data/
  viewer_contacts.csv
  viewer_bipolars.csv
  viewer_regions.csv
  viewer_patient_summary.csv
  viewer_data_audit.csv
  surfaces/
    <patient_id>_cortex_pial_high.npz
    <patient_id>_desikan_killiany_scouts.json
```

Surface files are optional for MNI point-cloud viewing, but SCS brain-surface viewing requires at least one cortex `.npz` per patient.

## Required Files

### `viewer_contacts.csv`

Required columns:

```text
patient_id, contact_name, shaft, contact_index,
mni_x, mni_y, mni_z,
scs_x, scs_y, scs_z,
dk_region, is_coordinate_valid
```

### `viewer_bipolars.csv`

Required columns:

```text
patient_id, canonical_bipolar_key, bipolar_channel,
anode, cathode, shaft,
mni_x, mni_y, mni_z,
brainstorm_scs_x, brainstorm_scs_y, brainstorm_scs_z,
region_bipolar, region_projected,
dk_region_from_brainstorm_bipolar,
is_doctor_burned, is_coordinate_valid
```

If you do not have surgical or ablation labels, set `is_doctor_burned` to `False`.

### `viewer_regions.csv`

Required columns:

```text
patient_id, region_projected, n_bipolars,
n_doctor_burned_bipolars,
x_centroid, y_centroid, z_centroid,
scs_x_centroid, scs_y_centroid, scs_z_centroid,
is_doctor_touched_region
```

### `viewer_patient_summary.csv`

Required columns:

```text
patient_id, n_contacts, n_bipolars, n_shafts,
n_doctor_burned_bipolars, n_touched_projected_regions,
top_doctor_region, top_doctor_region_burned_count,
coordinate_space, has_patient_surface_model, surface_model_note
```

### `viewer_data_audit.csv`

Required columns:

```text
patient_id, contacts, contacts_missing_mni,
bipolars, bipolars_missing_mni,
viewer_burned_bipolars, max_abs_delta_master_vs_brainstorm_mni,
has_patient_surface_model, n_projected_regions,
n_doctor_touched_regions, high_surface_found,
n_high_source_vertices, n_high_source_faces, high_surface_path
```

## Surface Format

Each cortex `.npz` should contain:

```text
vertices_scs_mm: float array shaped (n_vertices, 3)
faces: integer array shaped (n_faces, 3), zero-based triangle indices
```

Scout JSON files should be a list:

```json
{
  "label": "Synthetic temporal L",
  "normalized_label": "synthetic temporal l",
  "vertices": [0, 1, 2],
  "color": [0.2, 0.55, 0.9],
  "n_vertices": 3
}
```

## Optional Bad-Channel Spreadsheet

The bad-channel spreadsheet is optional and should stay local. The app accepts it through `--bad-channels` or future configuration UI.

Expected sheets:

- `bad_channels`
- `bad_bipolar_channels`

Expected `bad_channels` columns:

```text
patient, bad_channel_label, normalized_contact_name,
bad_channel_type, source_bipolar_label, source_endpoint_role,
source, source_folder, notes
```

Expected `bad_bipolar_channels` columns:

```text
patient, bad_bipolar_label, normalized_bipolar_label,
anode_contact, cathode_contact, brainstorm_channel_index,
n_data_files_checked, n_data_files_marked_bad, source, source_folder
```
