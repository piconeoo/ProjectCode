# AR Scene Practice Design

## Goal

Use scene words sent by the AR glasses to drive the Scenario Practice feature, while keeping manual scene input available as a fallback and optional override.

## Current Context

The current Scenario Practice page lives in `scenario_learning.py`. It asks the user to type a scene manually, then calls the large model to generate a vocabulary and sentence pack for that scene. `app.py` only routes to `scenario_learning.render_page(play_audio)`.

The AR object word flow is monitored in `AutoMonitor.py` from `data/Data1.json`. The new AR scene file is `data/Data2.json` and has this shape:

```json
{
  "app_id": "app2",
  "scene": "\u529e\u516c\u5ba4",
  "timestamp": 1779225049665
}
```

The current SQLite database only has `words` and `study_history`, so AR scenes need their own table.

## Selected Approach

Create a separate `scenes` table and let `AutoMonitor.py` monitor both AR feeds:

- `data/Data1.json` continues to update vocabulary words.
- `data/Data2.json` is checked every second by timestamp.
- New scene values are stored in `scenes`.
- Word and scene timestamp caches are separate so one feed cannot block the other.

## Data Model

Add a table:

```sql
CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene TEXT NOT NULL,
    source_app_id TEXT,
    source_timestamp INTEGER UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

`source_timestamp` is unique to avoid duplicate inserts when the monitor restarts.

## Scenario Practice Behavior

When the Scenario Practice page opens:

- Query `scenes` created today.
- If at least one scene exists, pick one randomly and show it as the recommended AR scene.
- The user can generate the practice pack from that AR scene.
- The manual input remains visible so the user can practice another scene.
- If no scene exists today, show a friendly message and let the user use manual input.

## Error Handling

If `Data2.json` is missing, invalid, or being written while read, the monitor should skip that tick and try again on the next second. Empty `scene` values should not be inserted. If an insert hits the unique timestamp constraint, it should be treated as already processed.

## Testing

Verify the scene helpers with a temporary SQLite database:

- Creating the `scenes` table works.
- Inserting a new scene stores `scene`, `app_id`, and `timestamp`.
- Reinserting the same timestamp does not duplicate data.
- Fetching today's scenes returns only rows created today.

Verify `scenario_learning.py` still imports successfully after the UI change.
