---
name: Calendar API limitations and WebSocket delete/edit
description: HA calendar write operations (delete, edit) are WebSocket-only; REST API only supports read and create via service
type: project
---

HA 2025.10.4 calendar API breakdown:
- **Read events**: `GET /api/calendars/{entity_id}?start=...&end=...` — works fine
- **Create events**: `POST /api/services/calendar/create_event` — works (REST service call)
- **Delete/edit events**: REST API returns 404 — not implemented

**Why:** The UI uses the WebSocket API for delete and edit. The REST API was never updated to expose these operations.

**WebSocket delete message format** (observed from browser):
```json
{"type": "calendar/event/delete", "entity_id": "calendar.life", "uid": "...", "recurrence_id": "", "recurrence_range": "", "id": 37}
```

**How to apply:** To implement `delete-event` and `edit-event`, we'd need to add WebSocket support (e.g. `websocket-client` for sync style). Connect to `ws://{host}/api/websocket`, authenticate with the bearer token, then send messages in the above format. User decided this isn't worth the complexity yet — leaving delete/edit unimplemented for now.
