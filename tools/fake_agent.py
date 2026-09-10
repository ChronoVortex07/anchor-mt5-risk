#!/usr/bin/env python3
"""Protocol simulator. Never connects to MT5 or a broker. Restart resets simulated positions."""

import argparse
import json
import os
import random
import time
import uuid
from pathlib import Path

import httpx
from app.domain import D, Market, Position, plan, simulate_execute


class FakeAgent:
    def __init__(self, client, credentials=None):
        self.client = client
        self.session_id = str(uuid.uuid4())
        self.credentials = credentials or {"installation_id": str(uuid.uuid4())}
        self.positions = [
            Position(str(i), "XAUUSD", "BUY", D("0.1"), D(2400 + i)) for i in range(1, 7)
        ]
        self.market = Market(D(2420), D("2420.2"), stops=D("0.1"))
        self.pending = None
        self.history = {}
        self.execution_enabled = False
        self.failure = None

    def state(self):
        return {
            "protocol_version": 1,
            "session_id": self.session_id,
            "installation_id": self.credentials["installation_id"],
            "ea_version": "fake-0.1",
            "account": {
                "login": 12345678,
                "server": "Fake-Demo",
                "margin_mode": "RETAIL_HEDGING",
                "trade_allowed": True,
                "expert_trade_allowed": True,
            },
        }

    def pair(self, code):
        response = self.client.post("/v1/agent/pair", json={**self.state(), "pairing_code": code})
        response.raise_for_status()
        self.credentials.update(response.json())
        return response.json()

    def tick(self):
        response = self.client.post(
            "/v1/agent/poll",
            json={
                **self.state(),
                "terminal": {"connected": True},
                "execution_enabled": self.execution_enabled,
                "result": self.pending,
            },
            headers={
                "X-Agent-ID": self.credentials["agent_id"],
                "Authorization": "Bearer " + self.credentials["agent_secret"],
            },
        )
        response.raise_for_status()
        data = response.json()
        if self.pending and data.get("ack_result_id") == self.pending["command_id"]:
            self.pending = None
        c = data.get("command")
        if not c:
            return data
        if c["id"] in self.history:
            self.pending = self.history[c["id"]]
            return data
        action = "be" if "BREAKEVEN" in c["type"] else "close"
        p = plan(
            self.positions,
            self.market,
            c["symbol"],
            c["side"],
            D(str(c["target_fraction"])),
            action,
        )
        preview = c["type"].startswith("PREVIEW_")
        summary = {
            "code": p.code,
            "symbol": c["symbol"],
            "side": p.side,
            "total_volume": float(p.total),
            "requested_volume": float(p.target),
            "already_protected_volume": float(p.already),
            "planned_volume": float(p.planned),
            "buy_volume": float(p.buy),
            "sell_volume": float(p.sell),
        }
        status = "SUCCEEDED" if p.code == "OK" else "FAILED"
        items = p.items
        if not preview:
            if not self.execution_enabled:
                status, summary["code"] = "FAILED", "EXECUTION_DISABLED"
            elif self.failure == "uncertain":
                status, summary["code"] = "UNCERTAIN", "EXECUTION_UNCERTAIN"
            else:
                rejected = (
                    frozenset(i.ticket for i in p.items)
                    if self.failure == "reject"
                    else frozenset()
                )
                self.positions, items, confirmed = simulate_execute(
                    self.positions, self.market, p, action, rejected
                )
                summary["confirmed_volume"] = float(confirmed)
                summary["changed_positions"] = sum(i.code == "CONFIRMED" for i in items)
                summary["protected_volume"] = (
                    float(
                        plan(
                            self.positions,
                            self.market,
                            c["symbol"],
                            c["side"],
                            D(1),
                            "be",
                        ).already
                    )
                    if action == "be"
                    else 0
                )
                achieved = D(str(summary["protected_volume"])) if action == "be" else confirmed
                status = (
                    "SUCCEEDED"
                    if p.total > 0 and achieved >= p.target
                    else "PARTIAL"
                    if confirmed
                    else "FAILED"
                )
                if summary["code"] == "OK" and status != "SUCCEEDED":
                    summary["code"] = "PARTIAL_COMPLETION" if confirmed else "EXECUTION_FAILED"
        summary["ineligible_positions"] = sum(
            i.code not in ("ELIGIBLE", "CONFIRMED", "ALREADY_PROTECTED") for i in items
        )
        self.pending = {
            "command_id": c["id"],
            "status": status,
            "summary": summary,
            "position_results": [
                {
                    "ticket": i.ticket,
                    "code": i.code,
                    "volume": float(i.volume) if preview or i.code == "CONFIRMED" else 0,
                }
                for i in items
            ],
        }
        self.history[c["id"]] = self.pending
        return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--pairing-code")
    parser.add_argument("--credentials", type=Path, default=Path("credentials.json"))
    parser.add_argument("--execute-simulation", action="store_true")
    parser.add_argument("--failure", choices=["reject", "uncertain"])
    args = parser.parse_args()
    credentials = json.loads(args.credentials.read_text()) if args.credentials.exists() else None
    with httpx.Client(base_url=args.url, timeout=3) as client:
        agent = FakeAgent(client, credentials)
        if not credentials:
            if not args.pairing_code:
                parser.error("--pairing-code required for first run")
            agent.pair(args.pairing_code)
            fd = os.open(args.credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump(agent.credentials, f)
        agent.execution_enabled, agent.failure = args.execute_simulation, args.failure
        delay = 1
        while True:
            try:
                response = agent.tick()
                print(json.dumps({"code": response["code"], "command": response.get("command")}))
                delay = response["poll_after_ms"] / 1000
            except httpx.HTTPError:
                delay = min(30, delay * 2)
            time.sleep(delay + random.random() * 0.3)


if __name__ == "__main__":
    main()
