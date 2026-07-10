import json
import sqlite3
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

sys.modules.setdefault(
    "openai",
    types.SimpleNamespace(OpenAI=lambda *args, **kwargs: object()),
)
streamlit_module = types.ModuleType("streamlit")
components_module = types.ModuleType("streamlit.components")
components_v1_module = types.ModuleType("streamlit.components.v1")
components_module.v1 = components_v1_module
streamlit_module.components = components_module
sys.modules.setdefault("streamlit", streamlit_module)
sys.modules.setdefault("streamlit.components", components_module)
sys.modules.setdefault("streamlit.components.v1", components_v1_module)

import AutoMonitor
from AutoMonitor import ensure_scene_table, insert_scene_record
from JsonImportToDataBase import WordImporter
from scenario_learning import fetch_today_scenes


class SceneStorageTests(unittest.TestCase):
    def test_auto_monitor_paths_are_project_relative(self):
        project_root = Path(__file__).resolve().parents[1]

        self.assertEqual(Path(AutoMonitor.WORD_JSON_FILE_PATH), project_root / "data" / "Data1.json")
        self.assertEqual(Path(AutoMonitor.SCENE_JSON_FILE_PATH), project_root / "data" / "Data2.json")
        self.assertEqual(Path(AutoMonitor.LAST_SCENE_TS_FILE), project_root / "last_scene_timestamp.txt")

    def test_insert_scene_record_deduplicates_by_timestamp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            conn = sqlite3.connect(db_path)
            ensure_scene_table(conn)

            self.assertIs(insert_scene_record(conn, "office", "app2", 1001), True)
            self.assertIs(insert_scene_record(conn, "office", "app2", 1001), False)

            rows = conn.execute(
                "SELECT scene, source_app_id, source_timestamp FROM scenes"
            ).fetchall()
            self.assertEqual(rows, [("office", "app2", 1001)])
            conn.close()

    def test_fetch_today_scenes_only_returns_today(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            conn = sqlite3.connect(db_path)
            ensure_scene_table(conn)
            conn.execute(
                "INSERT INTO scenes (scene, source_app_id, source_timestamp, created_at) VALUES (?, ?, ?, ?)",
                ("office", "app2", 1001, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.execute(
                "INSERT INTO scenes (scene, source_app_id, source_timestamp, created_at) VALUES (?, ?, ?, ?)",
                (
                    "airport",
                    "app2",
                    1002,
                    (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()
            conn.close()

            scenes = fetch_today_scenes(str(db_path))
            self.assertEqual([row["scene"] for row in scenes], ["office"])

    def test_process_scene_json_saves_new_timestamp_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "test.db"
            json_path = temp_path / "Data2.json"
            json_path.write_text(
                json.dumps({"app_id": "app2", "scene": "office", "timestamp": 2001}),
                encoding="utf-8",
            )

            original_db_path = AutoMonitor.DB_PATH
            original_scene_json_path = AutoMonitor.SCENE_JSON_FILE_PATH
            original_scene_ts_path = AutoMonitor.LAST_SCENE_TS_FILE
            try:
                AutoMonitor.DB_PATH = str(db_path)
                AutoMonitor.SCENE_JSON_FILE_PATH = str(json_path)
                AutoMonitor.LAST_SCENE_TS_FILE = str(temp_path / "last_scene_timestamp.txt")

                with redirect_stdout(StringIO()):
                    self.assertEqual(AutoMonitor.process_scene_json(0), 2001)
                    self.assertEqual(AutoMonitor.process_scene_json(2001), 2001)

                conn = sqlite3.connect(db_path)
                rows = conn.execute("SELECT scene, source_timestamp FROM scenes").fetchall()
                conn.close()
                self.assertEqual(rows, [("office", 2001)])
            finally:
                AutoMonitor.DB_PATH = original_db_path
                AutoMonitor.SCENE_JSON_FILE_PATH = original_scene_json_path
                AutoMonitor.LAST_SCENE_TS_FILE = original_scene_ts_path

    def test_process_scene_json_updates_when_timestamp_changes_downward(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "test.db"
            json_path = temp_path / "Data2.json"
            json_path.write_text(
                json.dumps({"app_id": "app2", "scene": "cinema", "timestamp": 3000}),
                encoding="utf-8",
            )

            original_db_path = AutoMonitor.DB_PATH
            original_scene_json_path = AutoMonitor.SCENE_JSON_FILE_PATH
            original_scene_ts_path = AutoMonitor.LAST_SCENE_TS_FILE
            try:
                AutoMonitor.DB_PATH = str(db_path)
                AutoMonitor.SCENE_JSON_FILE_PATH = str(json_path)
                AutoMonitor.LAST_SCENE_TS_FILE = str(temp_path / "last_scene_timestamp.txt")

                with redirect_stdout(StringIO()):
                    self.assertEqual(AutoMonitor.process_scene_json(4000), 3000)

                conn = sqlite3.connect(db_path)
                rows = conn.execute("SELECT scene, source_timestamp FROM scenes").fetchall()
                conn.close()
                self.assertEqual(rows, [("cinema", 3000)])
            finally:
                AutoMonitor.DB_PATH = original_db_path
                AutoMonitor.SCENE_JSON_FILE_PATH = original_scene_json_path
                AutoMonitor.LAST_SCENE_TS_FILE = original_scene_ts_path

    def test_word_importer_accepts_path_objects(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "test.db"
            json_path = temp_path / "words.json"
            json_path.write_text(
                json.dumps(
                    {
                        "laptop": {
                            "phonetic": "/lap.top/",
                            "meaning": "notebook computer",
                            "example": "I use a laptop for work.",
                            "example_cn": "I use a laptop for work.",
                            "part_of_speech": "n. noun",
                            "difficulty": 2,
                        }
                    }
                ),
                encoding="utf-8",
            )

            importer = WordImporter(db_path=db_path)
            with redirect_stdout(StringIO()):
                success, message = importer.import_json_file(json_path, update_existing=True)

            self.assertTrue(success, message)
            conn = sqlite3.connect(db_path)
            rows = conn.execute("SELECT word, meaning FROM words").fetchall()
            conn.close()
            self.assertEqual(rows, [("laptop", "notebook computer")])


if __name__ == "__main__":
    unittest.main()
