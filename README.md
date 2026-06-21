# Patient Electrode Desktop Viewer

[中文说明](README.zh-CN.md)

A Windows desktop 3D viewer for patient-level SEEG contacts, bipolar channels, anatomical regions, synthetic sample data, and optional local clinical annotations.

The public repository contains source code and packaging files only. It does not include real patient data.

## Download

For end users, download the latest Windows installer from GitHub Releases:

```text
PatientElectrodeViewer-Setup-x.y.z.exe
```

After installation, launch the app and select your local `viewer_data` folder when prompted. The app also ships with synthetic `sample_data` so users can verify that the installation works before preparing their own data.

## Data Policy

Do not upload protected health information, identifiable anatomy, raw clinical exports, Brainstorm databases, electrode coordinate tables, surgical labels, or bad-channel spreadsheets to a public repository.

Users are responsible for preparing de-identified data and confirming that they have permission to use it under their institution, IRB, ethics, privacy, and data-use requirements.

This software is a research visualization tool. It is not a medical device and must not be used for clinical decision-making without independent validation and appropriate approval.

## User Data Folder

Prepare a local folder:

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

See [docs/DATA_PREPARATION.md](docs/DATA_PREPARATION.md) for required columns and surface file formats.

## Running From Source

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/105_patient_electrode_desktop_viewer.py --data-dir sample_data
```

If `--data-dir` is omitted, the app uses the saved user config or prompts for a folder.

Optional bad-channel annotation:

```bash
python src/105_patient_electrode_desktop_viewer.py --data-dir viewer_data --bad-channels path\to\bad_channels.xlsx
```

## Building The Windows App

Install build tools:

```bash
pip install -r requirements.txt
pip install pyinstaller
```

Build the app folder:

```bash
pyinstaller packaging\patient_electrode_viewer.spec --noconfirm
```

Build the installer with Inno Setup:

```text
ISCC.exe packaging\installer.iss
```

GitHub Actions can build the same installer when a version tag such as `v0.1.0` is pushed.
