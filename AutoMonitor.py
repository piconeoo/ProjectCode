import json
import os
import re
import sqlite3
import time
from pathlib import Path

from openai import OpenAI

from JsonImportToDataBase import WordImporter


BASE_DIR = Path(__file__).resolve().parent
WORD_JSON_FILE_PATH = BASE_DIR / "data" / "Data1.json"
SCENE_JSON_FILE_PATH = BASE_DIR / "data" / "Data2.json"
DB_PATH = BASE_DIR / "vocabulary.db"
LAST_WORD_TS_FILE = BASE_DIR / "last_word_timestamp.txt"
LAST_SCENE_TS_FILE = BASE_DIR / "last_scene_timestamp.txt"
LEGACY_LAST_TS_FILE = BASE_DIR / "last_timestamp.txt"
POLL_INTERVAL_SECONDS = 1


client = OpenAI(
    api_key="sk-698867d6d2d24eefbf53f360b4fa276c",
    base_url="https://dashscope.aliyuncs.com/api/v2/apps/protocols/compatible-mode/v1",
)


def get_word_details(word: str) -> dict:
    prompt = f"""
    Please provide detailed learning information for the English word "{word}".
    Return only a valid JSON object with these fields:

    1. phonetic: IPA pronunciation.
    2. meaning: concise Chinese meaning.
    3. example: one natural English example sentence.
    4. example_cn: Chinese translation of the example sentence.
    5. part_of_speech: part of speech, such as "n. noun" or "adj. adjective".
    6. difficulty: an integer from 1 to 5.

    Example:
    {{
        "phonetic": "/ˈmɒn.ɪ.tər/",
        "meaning": "显示器；监视器",
        "example": "I need to buy a new monitor for my computer.",
        "example_cn": "我需要为我的电脑买一个新显示器。",
        "part_of_speech": "n. noun",
        "difficulty": 2
    }}
    """

    try:
        response = client.responses.create(
            model="qwen-flash",
            input=prompt,
        )
        result_text = response.output_text.strip()
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if not json_match:
            print(f"[words] Could not extract JSON from response: {result_text}")
            return default_word_details("unknown")

        word_details = json.loads(json_match.group())
        for field in ['phonetic', 'meaning', 'example', 'example_cn', 'part_of_speech']:
            if field not in word_details:
                word_details[field] = "unknown"

        if 'difficulty' not in word_details or not isinstance(word_details['difficulty'], int):
            word_details['difficulty'] = 1

        return word_details
    except Exception as e:
        print(f"[words] Failed to get details for '{word}': {e}")
        return default_word_details("error")


def default_word_details(value):
    return {
        "phonetic": value,
        "meaning": value,
        "example": value,
        "example_cn": value,
        "part_of_speech": value,
        "difficulty": 1,
    }


def read_timestamp(file_path, fallback_path=None):
    paths = [file_path]
    if fallback_path:
        paths.append(fallback_path)

    for path in paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content.isdigit():
                    return int(content)
    return 0


def write_timestamp(file_path, timestamp):
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(str(timestamp))


def read_json_file(file_path):
    if not os.path.exists(file_path):
        return None

    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def ensure_scene_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scenes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scene TEXT NOT NULL,
        source_app_id TEXT,
        source_timestamp INTEGER UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
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


def process_word_json(last_ts):
    data = read_json_file(WORD_JSON_FILE_PATH)
    if not data:
        return last_ts

    current_ts = data.get('timestamp', 0)
    if current_ts == last_ts:
        return last_ts

    print(f"\n[words] Detected update: {current_ts}")
    words_list = data.get('words', [])
    english_words = [item.get('english') for item in words_list if item.get('english')]

    if not english_words:
        print("[words] No English words found, skipping.")
        write_timestamp(LAST_WORD_TS_FILE, current_ts)
        return current_ts

    all_results = {}
    for i, word in enumerate(english_words, 1):
        print(f"   Requesting word details [{i}/{len(english_words)}]: {word}")
        all_results[word] = get_word_details(word)
        time.sleep(1)

    temp_json = BASE_DIR / "words_with_details.json"
    with open(temp_json, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    importer = WordImporter(db_path=DB_PATH)
    success, msg = importer.import_json_file(temp_json, update_existing=True)

    if success:
        write_timestamp(LAST_WORD_TS_FILE, current_ts)
        print("[words] Database updated.")
        return current_ts

    print(f"[words] Database import failed: {msg}")
    return last_ts


def process_scene_json(last_ts):
    data = read_json_file(SCENE_JSON_FILE_PATH)
    if not data:
        return last_ts

    current_ts = data.get('timestamp', 0)
    if current_ts == last_ts:
        return last_ts

    scene = data.get('scene', '')
    app_id = data.get('app_id', '')

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        inserted = insert_scene_record(conn, scene, app_id, current_ts)
    finally:
        conn.close()

    write_timestamp(LAST_SCENE_TS_FILE, current_ts)
    if inserted:
        print(f"[scene] Saved AR scene: {scene}")
    else:
        print("[scene] Scene was empty or already saved.")
    return current_ts


def monitor_and_update():
    print("AR word and scene monitor started.")
    last_word_ts = read_timestamp(LAST_WORD_TS_FILE, LEGACY_LAST_TS_FILE)
    last_scene_ts = read_timestamp(LAST_SCENE_TS_FILE)

    print(f"Watching words: {WORD_JSON_FILE_PATH} (last timestamp: {last_word_ts})")
    print(f"Watching scenes: {SCENE_JSON_FILE_PATH} (last timestamp: {last_scene_ts})")

    while True:
        try:
            last_word_ts = process_word_json(last_word_ts)
        except json.JSONDecodeError:
            print("\r[words] Waiting for valid JSON...", end="")
        except Exception as e:
            print(f"\r[words] Monitor error: {e}", end="")

        try:
            last_scene_ts = process_scene_json(last_scene_ts)
        except json.JSONDecodeError:
            print("\r[scene] Waiting for valid JSON...", end="")
        except Exception as e:
            print(f"\r[scene] Monitor error: {e}", end="")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    monitor_and_update()
