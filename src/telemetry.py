"""H7 counts-only telemetry (docs/phases/16_post_launch_roadmap.md, H7).

Two kinds of line, each one JSON object on STDOUT, prefixed "DRLCA_SIGNAL ".
Render captures stdout in its logs, so there is no new service, no network
call and no file:

  turn     emitted once when a NEW turn is computed (never on replay):
           route, refused, top-score bucket, excerpts shown, organisations
           shown, whether an AI answer was produced.
  helpful  emitted when the user answers "Was this answer helpful?".

Both carry `id`, a random per-turn token that only joins those two lines.
There is no session id, no user id, no IP and no history.

THE QUESTION TEXT IS NEVER LOGGED unless the user ticked the separate,
explicit "share my question text" opt-in, and then only that turn's question,
truncated. Conversation history is never logged: nothing here reads
st.session_state. This population discloses abuse and coercion; a log that
holds no words cannot leak any.
"""
import json
import uuid

PREFIX = "DRLCA_SIGNAL "
SCHEMA_VERSION = 1
QUESTION_MAX = 300
# The ONLY keys a line may carry. test_phase09_ops asserts against this.
TURN_FIELDS = {"v", "kind", "id", "route", "refused", "top", "shown", "orgs", "ai", "q"}
HELPFUL_FIELDS = {"v", "kind", "id", "helpful"}
HELPFUL_VALUES = {"Yes": "yes", "No": "no"}


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def score_bucket(top) -> str:
    """Coarse band of the best excerpt score: never the score itself."""
    if top is None:
        return "none"
    if top < 0.10:
        return "<0.10"
    if top < 0.20:
        return "0.10-0.20"
    if top < 0.30:
        return "0.20-0.30"
    return ">=0.30"


def turn_record(signal_id: str, route: str, refused: bool, top, shown: int, orgs: int,
                ai: bool, question: str = "", share_text: bool = False) -> dict:
    rec = {"v": SCHEMA_VERSION, "kind": "turn", "id": signal_id, "route": route,
           "refused": bool(refused), "top": score_bucket(top), "shown": int(shown),
           "orgs": int(orgs), "ai": bool(ai)}
    if share_text and question:
        rec["q"] = question[:QUESTION_MAX]
    return rec


def helpful_record(signal_id: str, choice) -> dict:
    return {"v": SCHEMA_VERSION, "kind": "helpful", "id": signal_id,
            "helpful": HELPFUL_VALUES.get(choice, "none")}


def line(rec: dict) -> str:
    return PREFIX + json.dumps(rec, separators=(",", ":"), ensure_ascii=False)


def emit(rec: dict) -> None:
    """Print one line to stdout. Never raises into the UI."""
    try:
        print(line(rec), flush=True)
    except Exception:  # noqa: BLE001 -- telemetry must never break a turn
        pass
