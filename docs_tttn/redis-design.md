# Redis Design

## Key Namespaces
- `parking:live:slot:S01` .. `parking:live:slot:S09` (Hash, TTL 15s when synced from desktop, updated on billing session start/end):
  - `status`: `"EMPTY"` | `"OCCUPIED"`
  - `session_id`: Active UUID session identifier (or `""` when empty)
  - `started_at`: UTC ISO-8601 timestamp when session started
  - `updated_at`: UTC ISO-8601 timestamp of last state update
  - `observed_at`: UTC ISO-8601 timestamp from detector snapshot
  - `source`: `"desktop-droidcam"` or `"parking_billing_service"`
- `parking:live:meta` (Hash):
  - `observed_at`: Latest snapshot timestamp
  - `source`: Snapshot producer identifier
- `slot:{slot_id}:state` & `slot:{slot_id}:session` (Strings):
  - Maintained by `parking_billing_service` during session lifecycle transitions.
- `lock:slot:{slot_id}` (String with `NX` and `EX=10`):
  - Distributed mutex acquired via `acquire_lock()` in `parking_billing_service` and released via atomic Lua compare-and-delete script.
