import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "patient_electrode_viewer_config.py"


def load_viewer_module():
    spec = importlib.util.spec_from_file_location("patient_electrode_desktop_viewer", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ViewerDataValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.viewer = load_viewer_module()

    def test_valid_data_dir_accepts_required_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            for name, columns in self.viewer.REQUIRED_COLUMNS.items():
                (data_dir / name).write_text(",".join(sorted(columns)) + "\n", encoding="utf-8")

            result = self.viewer.validate_data_dir(data_dir)

            self.assertTrue(result.samefile(data_dir))

    def test_missing_required_file_reports_all_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "viewer_contacts.csv").write_text("patient_id\nsample\n", encoding="utf-8")

            with self.assertRaises(self.viewer.DataValidationError) as cm:
                self.viewer.validate_data_dir(data_dir)

            message = str(cm.exception)
            self.assertIn("viewer_bipolars.csv", message)
            self.assertIn("viewer_regions.csv", message)
            self.assertIn("viewer_patient_summary.csv", message)
            self.assertIn("viewer_data_audit.csv", message)

    def test_missing_required_columns_reports_file_and_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            for name in self.viewer.REQUIRED_DATA_FILES:
                (data_dir / name).write_text("patient_id\nsample\n", encoding="utf-8")

            with self.assertRaises(self.viewer.DataValidationError) as cm:
                self.viewer.validate_data_dir(data_dir)

            message = str(cm.exception)
            self.assertIn("viewer_contacts.csv", message)
            self.assertIn("contact_name", message)
            self.assertIn("viewer_bipolars.csv", message)
            self.assertIn("bipolar_channel", message)


if __name__ == "__main__":
    unittest.main()
