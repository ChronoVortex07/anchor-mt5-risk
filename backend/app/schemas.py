from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Symbol = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.#-]+$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AccountState(Strict):
    login: int = Field(gt=0)
    server: str = Field(min_length=1, max_length=120)
    margin_mode: str = Field(max_length=64)
    trade_allowed: bool
    expert_trade_allowed: bool


class Terminal(Strict):
    connected: bool


class Pair(Strict):
    protocol_version: Literal[1]
    pairing_code: str = Field(pattern=r"^[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$")
    installation_id: UUID
    session_id: UUID
    ea_version: str = Field(min_length=1, max_length=32)
    account: AccountState


class PositionResult(Strict):
    ticket: str = Field(max_length=24)
    code: str = Field(max_length=64)
    volume: float = Field(ge=0)
    retcode: int = 0
    old_sl: float = 0
    new_sl: float = 0
    tp: float = 0


class Summary(Strict):
    code: str = Field(default="OK", max_length=64)
    symbol: str = Field(default="", max_length=64)
    side: Literal["BUY", "SELL", "BOTH", "AUTO"] = "AUTO"
    total_volume: float = Field(default=0, ge=0)
    requested_volume: float = Field(default=0, ge=0)
    already_protected_volume: float = Field(default=0, ge=0)
    planned_volume: float = Field(default=0, ge=0)
    confirmed_volume: float = Field(default=0, ge=0)
    protected_volume: float = Field(default=0, ge=0)
    buy_volume: float = Field(default=0, ge=0)
    sell_volume: float = Field(default=0, ge=0)
    changed_positions: int = Field(default=0, ge=0)
    ineligible_positions: int = Field(default=0, ge=0)


class Submission(Strict):
    command_id: UUID
    status: Literal["SUCCEEDED", "PARTIAL", "FAILED", "UNCERTAIN"]
    summary: Summary
    position_results: list[PositionResult] = Field(default_factory=list, max_length=128)


class Poll(Strict):
    protocol_version: Literal[1]
    installation_id: UUID
    session_id: UUID
    ea_version: str = Field(min_length=1, max_length=32)
    account: AccountState
    terminal: Terminal
    execution_enabled: bool
    result: Submission | None = None


class Intent(Strict):
    symbol: Symbol
    side: Literal["AUTO", "BUY", "SELL", "BOTH"] = "AUTO"
    target_fraction: float = Field(gt=0, le=1)
    # Configured locally in the EA; backend cannot choose arbitrary stop prices/buffers.


class AliasInput(Strict):
    alias: Symbol
    actual_symbol: Symbol


class Login(Strict):
    id: int = Field(gt=0)
    auth_date: int
    hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    first_name: str = Field(max_length=256)
    last_name: str | None = Field(default=None, max_length=256)
    username: str | None = Field(default=None, max_length=64)
    photo_url: str | None = Field(default=None, max_length=2048)
