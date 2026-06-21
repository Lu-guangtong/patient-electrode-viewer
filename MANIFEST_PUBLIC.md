# Public Repository Manifest

Use this file as the allow-list when creating the public GitHub repository. Do not push the full local research workspace.

## Include

```text
README.md
requirements.txt
run_viewer.bat
.gitignore.public (copy to .gitignore in the public repository)
.github/workflows/build-windows.yml
docs/DATA_PREPARATION.md
packaging/installer.iss
packaging/patient_electrode_viewer.spec
sample_data/
src/105_patient_electrode_desktop_viewer.py
src/patient_electrode_viewer_config.py
tests/test_viewer_config.py
tools/make_sample_viewer_data.py
31_patient_electrode_viewer/patient_electrode_viewer.ico
31_patient_electrode_viewer/patient_electrode_viewer_icon.png
```

## Exclude

```text
31_patient_electrode_viewer/data/
31_patient_electrode_viewer/PATIENT_ELECTRODE_VIEWER_DATA_REPORT.md
raw_data/
brainstorm_electrode_region_labels/
03_bipolar/
29_doctor_burned_region_distribution/
30_region_network_suspicion_ranking/
all patient-level result folders
all clinical spreadsheets
all EDF, MAT, NIfTI, DICOM, XLSX, CSV, TSV files that are not synthetic sample data
```

The public repository should be a clean app repository, not the full analysis workspace.
