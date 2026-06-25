# AR Scene Practice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store AR scene updates from `data/Data2.json` and use today's stored scenes as the default source for Scenario Practice.

**Architecture:** Add a focused scene persistence layer to the existing SQLite database. Extend `AutoMonitor.py` so object words and scene updates are monitored independently. Update `scenario_learning.py` to offer a random AR scene from today's stored rows while keeping manual input available.

**Tech Stack:** Python, SQLite, Streamlit, existing OpenAI/DashScope client code.

---

## File Structure

- Modify `CreateDataBase.py`: add the `scenes` table during database initialization.
- Modify `AutoMonitor.py`: add scene table creation, scene insertion, independent timestamp tracking, and 1-second polling.
- Modify `scenario_learning.py`: add SQLite helpers for today's scenes and update the UI flow.
- Create `tests/test_scene_storage.py`: verify scene table behavior with a temporary SQLite database.

### Task 1: Scene Storage Helpers

**Files:**
- Modify: `AutoMonitor.py`
- Test: `tests/test_scene_storage.py`

- [ ] **Step 1: Write the storage tests**

Create `tests/test_scene_storage.py`:

```python
import sqlite3
from datetime import datetime, timedelta

from AutoMonitor import ensure_scene_table, insert_scene_record
from scenario_learning import fetch_today_scenes


def test_insert_scene_record_deduplicates_by_timestamp(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    ensure_scene_table(conn)

    assert insert_scene_record(conn, "office", "app2", 1001) is True
    assert insert_scene_record(conn, "office", "app2", 1001) is False

    rows = conn.execute("SELECT scene, source_app_id, source_timestamp FROM scenes").fetchall()
    assert rows == [("office", "app2", 1001)]


def test_fetch_today_scenes_only_returns_today(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    ensure_scene_table(conn)
    conn.execute(
        "INSERT INTO scenes (scene, source_app_id, source_timestamp, created_at) VALUES (?, ?, ?, ?)",
        ("office", "app2", 1001, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.execute(
        "INSERT INTO scenes (scene, source_app_id, source_timestamp, created_at) VALUES (?, ?, ?, ?)",
        ("airport", "app2", 1002, (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()

    scenes = fetch_today_scenes(str(db_path))
    assert [row["scene"] for row in scenes] == ["office"]
```

- [ ] **Step 2: Run tests to verify they fail before implementation**

Run: `python -m unittest tests.test_scene_storage -v`

Expected: import errors or missing function failures.

- [ ] **Step 3: Implement `ensure_scene_table` and `insert_scene_record`**

Add focused functions in `AutoMonitor.py`:

```python
def ensure_scene_table(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene TEXT NOT NULL,
            source_app_id TEXT,
            source_timestamp INTEGER UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def insert_scene_record(conn, scene, app_id, timestamp):
    scene = (scene or "").strip()
    if not scene or not timestamp:
        return False

    ensure_scene_table(conn)
    try:
        conn.execute(
            "INSERT INTO scenes (scene, source_app_id, source_timestamp) VALUES (?, ?, ?)",
            (scene, app_id, timestamp),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
```

- [ ] **Step 4: Implement `fetch_today_scenes`**

Add a helper to `scenario_learning.py`:

```python
def fetch_today_scenes(db_path=DB_PATH):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scene TEXT NOT NULL,
                source_app_id TEXT,
                source_timestamp INTEGER UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        rows = conn.execute("""
            SELECT id, scene, source_app_id, source_timestamp, created_at
            FROM scenes
            WHERE date(created_at) = date('now', 'localtime')
            ORDER BY created_at DESC
        """).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests to verify storage passes**

Run: `python -m unittest tests.test_scene_storage -v`

Expected: all tests pass.

### Task 2: Monitor `Data2.json`

**Files:**
- Modify: `AutoMonitor.py`

- [ ] **Step 1: Add scene monitor config**

Use separate constants:

```python
WORD_JSON_FILE_PATH = "data/Data1.json"
SCENE_JSON_FILE_PATH = "data/Data2.json"
LAST_WORD_TS_FILE = "last_word_timestamp.txt"
LAST_SCENE_TS_FILE = "last_scene_timestamp.txt"
POLL_INTERVAL_SECONDS = 1
```

- [ ] **Step 2: Split monitor work into small functions**

Keep word import behavior intact in `process_word_json(last_ts)` and add `process_scene_json(last_ts)`.

- [ ] **Step 3: Update the main loop**

Each loop checks both files and sleeps one second:

```python
last_word_ts = read_timestamp(LAST_WORD_TS_FILE)
last_scene_ts = read_timestamp(LAST_SCENE_TS_FILE)

while True:
    last_word_ts = process_word_json(last_word_ts)
    last_scene_ts = process_scene_json(last_scene_ts)
    time.sleep(POLL_INTERVAL_SECONDS)
```

- [ ] **Step 4: Compile-check the monitor**

Run: `python -m py_compile AutoMonitor.py`

Expected: no output and exit code 0.

### Task 3: Scenario Practice UI

**Files:**
- Modify: `scenario_learning.py`

- [ ] **Step 1: Import dependencies**

Add:

```python
import random
import sqlite3
```

- [ ] **Step 2: Initialize AR scene state**

In `render_page`, load today's scenes and pick a random scene when needed:

```python
today_scenes = fetch_today_scenes()
if today_scenes and not st.session_state.get("selected_ar_scene"):
    st.session_state["selected_ar_scene"] = random.choice(today_scenes)["scene"]
```

- [ ] **Step 3: Add AR scene controls**

Show the selected AR scene, a button to regenerate from it, and a button to pick another random scene.

- [ ] **Step 4: Keep manual input**

Keep the existing manual `text_input` and generation button so the user can override the AR recommendation.

- [ ] **Step 5: Compile-check the page**

Run: `python -m py_compile scenario_learning.py`

Expected: no output and exit code 0.

### Task 4: Database Initialization

**Files:**
- Modify: `CreateDataBase.py`

- [ ] **Step 1: Add the `scenes` table to `init_database`**

Use the same schema as the monitor helper.

- [ ] **Step 2: Verify init script compiles**

Run: `python -m py_compile CreateDataBase.py`

Expected: no output and exit code 0.

### Task 5: End-to-End Verification

**Files:**
- No new file changes expected.

- [ ] **Step 1: Run all targeted tests**

Run:

```bash
python -m unittest tests.test_scene_storage -v
python -m py_compile AutoMonitor.py scenario_learning.py CreateDataBase.py app.py
```

Expected: tests pass and compile checks exit 0.

- [ ] **Step 2: Manually probe scene insertion**

Run a short Python command against `vocabulary.db` that inserts a sample scene with a unique timestamp and reads today's scenes through `scenario_learning.fetch_today_scenes`.

Expected: the inserted scene appears in the returned list.
