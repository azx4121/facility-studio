"""Shared OA regressions, also executed by the delivered EXE/App."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from facility_studio.airflow_acceptance import AirflowBalance

if __name__ == "__main__":
    unittest.main()
