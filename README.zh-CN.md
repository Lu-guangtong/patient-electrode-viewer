# 患者电极桌面查看器

一个 Windows 桌面 3D 查看器，用于查看患者级 SEEG 单极触点、双极通道、解剖脑区、合成示例数据，以及可选的本地临床标注。

公开仓库只包含源代码和打包文件，不包含真实患者数据。

## 下载

用户可以从 GitHub Releases 下载最新 Windows 安装包：

```text
PatientElectrodeViewer-Setup-x.y.z.exe
```

安装后启动应用，并在提示时选择你本地的 `viewer_data` 文件夹。应用也自带合成的 `sample_data`，用户可以先用它验证安装是否正常，再准备自己的数据。

## 数据政策

本查看器不包含真实的个体解剖、原始临床导出、Brainstorm 数据库、电极坐标表、手术标签或坏导表。

用户需要自行准备去标识化数据，并确认其数据使用符合所在机构、伦理/IRB、隐私和数据使用规定。

本软件是研究可视化工具，不是医疗器械；未经独立验证和相应审批，不得用于临床决策。

## 用户数据文件夹

准备一个本地文件夹：

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

必需字段和脑表面文件格式见 [docs/DATA_PREPARATION.md](docs/DATA_PREPARATION.md)。

## 从源码运行

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/105_patient_electrode_desktop_viewer.py --data-dir sample_data
```

如果省略 `--data-dir`，应用会使用已保存的用户配置，或弹窗提示选择文件夹。

可选坏导标注：

```bash
python src/105_patient_electrode_desktop_viewer.py --data-dir viewer_data --bad-channels path\to\bad_channels.xlsx
```

## 构建 Windows 应用

安装构建工具：

```bash
pip install -r requirements.txt
pip install pyinstaller
```

构建应用目录：

```bash
pyinstaller packaging\patient_electrode_viewer.spec --noconfirm
```

使用 Inno Setup 构建安装包：

```text
ISCC.exe packaging\installer.iss
```

推送类似 `v0.1.0` 的版本标签后，GitHub Actions 可以构建同样的安装包。
