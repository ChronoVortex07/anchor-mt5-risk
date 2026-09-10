"""Operator-only resolution after inspecting MT5 positions AND broker deal history.

This is intentionally not a remote agent/dashboard action. It never submits trades.
"""

import argparse
import json
from pathlib import Path

from app import service
from app.db import Session, now
from app.models import Account, Command
from sqlalchemy import select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command_id")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--acknowledge-broker-history-checked", action="store_true", required=True)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text())
    if not all(
        evidence.get(key) for key in ("operator", "checked_at_utc", "broker_deals", "conclusion")
    ):
        parser.error("Evidence requires operator, checked_at_utc, broker_deals, conclusion")
    if len(json.dumps(evidence)) > 16000:
        parser.error("Evidence too large")
    with Session.begin() as db:
        command = db.get(Command, args.command_id)
        if not command:
            parser.error("Unknown command")
        account = db.scalar(
            select(Account).where(Account.id == command.account_id).with_for_update()
        )
        db.refresh(command)
        service.expire(db, account)
        if command.status != "UNCERTAIN":
            parser.error("Only UNCERTAIN commands can be reconciled")
        command.status, command.completed_at = "CANCELLED", now()
        account.status = "OFFLINE"
        service.audit(
            db,
            "OPERATOR_RECONCILED",
            account_id=account.id,
            command_id=command.id,
            user_id=command.user_id,
            details=evidence,
        )
        service.notify(
            db,
            command.user_id,
            "An operator reconciled the uncertain operation against "
            "broker history. No additional trade was sent. Refresh the account before continuing.",
        )
    print("Reconciliation recorded. Preserve the evidence and reconcile the local EA journal too.")


if __name__ == "__main__":
    main()
