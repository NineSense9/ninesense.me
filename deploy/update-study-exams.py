"""Apply reviewed national exam dates while preserving the owner's exam entry."""

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--events", type=Path, default=Path(__file__).with_name("study-exams-2027.json"))
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("Existing study database is required")
    payload = json.loads(args.events.read_text(encoding="utf-8-sig"))
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(args.database) as db:
        db.execute("PRAGMA busy_timeout=5000")
        exam = db.execute(
            "SELECT start_date FROM exam_events "
            "WHERE active=1 AND countdown_target=1 AND kind='exam'"
        ).fetchone()
        events = list(payload["events"])
        if exam:
            ticket = dict(payload["admission_ticket"])
            exam_date = date.fromisoformat(exam[0])
            ticket["start_date"] = (exam_date - timedelta(days=10)).isoformat()
            ticket["end_date"] = None
            events.append(ticket)
        for event in events:
            existing = db.execute(
                "SELECT id FROM exam_events WHERE kind=? AND title=? AND active=1",
                (event["kind"], event["title"]),
            ).fetchall()
            if len(existing) > 1:
                raise ValueError(f"Multiple active entries for {event['title']}; review before updating")
            values = (
                event["date_status"], event["start_date"], event.get("end_date"),
                event["description"], event["source_url"], event["position"], now,
            )
            if existing:
                db.execute(
                    "UPDATE exam_events SET date_status=?, start_date=?, end_date=?, "
                    "description=?, source_url=?, position=?, updated_at=? WHERE id=?",
                    (*values, existing[0][0]),
                )
            else:
                db.execute(
                    "INSERT INTO exam_events (date_status,start_date,end_date,description,"
                    "source_url,position,updated_at,kind,title,countdown_target,active,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,0,1,?)",
                    (*values, event["kind"], event["title"], now),
                )
            print(f"Updated: {event['title']}")
        print("Existing exam date and countdown preserved.")


if __name__ == "__main__":
    main()
