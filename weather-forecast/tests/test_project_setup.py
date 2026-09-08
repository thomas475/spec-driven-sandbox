from __future__ import annotations

import importlib
import sys
import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"


class ProjectSetupTests(unittest.TestCase):
    def test_package_imports_from_configured_source_layout(self) -> None:
        sys.path.insert(0, str(SOURCE_ROOT))
        self.addCleanup(sys.path.remove, str(SOURCE_ROOT))

        package = importlib.import_module("weather_forecast")

        self.assertEqual(
            Path(package.__file__).resolve(),
            SOURCE_ROOT / "weather_forecast" / "__init__.py",
        )

    def test_project_metadata_has_required_python_and_runtime_dependency(self) -> None:
        with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject_file:
            pyproject = tomllib.load(pyproject_file)

        project = pyproject["project"]
        self.assertEqual(project["requires-python"], ">=3.13")
        self.assertEqual(project["dependencies"], ["PySide6>=6.8"])
        self.assertEqual(
            pyproject["tool"]["setuptools"]["packages"]["find"]["where"],
            ["src"],
        )


if __name__ == "__main__":
    unittest.main()

