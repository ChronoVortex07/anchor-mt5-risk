import asyncio
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zipfile import ZipFile

import pytest
from app.config import Settings
from package_ea import ROOT, package
from package_local_panel import INCLUDES
from package_local_panel import package as package_local_panel
from pydantic import SecretStr
from register_webhook import configure, validate_config


def configuration(**overrides):
    values = dict(
        public_url="https://risk.example.com",
        telegram_bot_username="AnchorTestBot",
        telegram_bot_token=SecretStr("123:fake-test-token"),
        telegram_webhook_secret=SecretStr("x" * 40),
    )
    return Settings(**(values | overrides))


def bot():
    instance = AsyncMock()
    instance.get_me.return_value = SimpleNamespace(username="AnchorTestBot")
    instance.get_webhook_info.return_value = SimpleNamespace(
        url="https://risk.example.com/v1/telegram/webhook",
        pending_update_count=0,
        last_error_date=None,
    )
    return instance


def test_setup_verifies_identity_and_registers_three_commands():
    fake = bot()
    result = asyncio.run(configure(fake, configuration(), drop_pending=True))
    commands = fake.set_my_commands.call_args.args[0]
    assert [c.command for c in commands] == ["link", "be", "close"]
    assert fake.set_webhook.call_args.kwargs["secret_token"] == "x" * 40
    assert fake.set_webhook.call_args.kwargs["drop_pending_updates"] is True
    assert result["bot_url"] == "https://t.me/AnchorTestBot"
    assert "fake-test-token" not in str(result) and "x" * 40 not in str(result)


def test_check_does_not_mutate_telegram():
    fake = bot()
    assert asyncio.run(configure(fake, configuration(), check=True))["mode"] == "checked"
    fake.set_webhook.assert_not_called()
    fake.set_my_commands.assert_not_called()
    fake.set_my_description.assert_not_called()


def test_mismatching_bot_aborts_before_mutation():
    fake = bot()
    fake.get_me.return_value.username = "SomeOtherBot"
    with pytest.raises(ValueError, match="does not match"):
        asyncio.run(configure(fake, configuration()))
    fake.set_webhook.assert_not_called()


def test_registration_preserves_pending_updates_unless_explicit():
    fake = bot()
    asyncio.run(configure(fake, configuration()))
    assert fake.set_webhook.call_args.kwargs["drop_pending_updates"] is False


@pytest.mark.parametrize(
    "url",
    [
        "http://risk.example.com",
        "https://localhost",
        "https://127.0.0.1",
        "https://a:b@risk.example.com",
        "https://risk.example.com/foo",
        "https://risk.example.com?token=x",
    ],
)
def test_setup_rejects_inappropriate_public_origins(url):
    with pytest.raises(ValueError, match="public HTTPS origin"):
        validate_config(configuration(public_url=url))


@pytest.mark.parametrize("secret", ["short", " " * 40, "x" * 257])
def test_webhook_secret_constraints(secret):
    with pytest.raises(ValueError, match="webhook secret"):
        validate_config(configuration(telegram_webhook_secret=SecretStr(secret)))


def test_ea_archive_complete_reproducible_and_source_only(tmp_path):
    archive, checksum = package(tmp_path / "first")
    other, _ = package(tmp_path / "second")
    assert archive.read_bytes() == other.read_bytes()
    assert hashlib.sha256(archive.read_bytes()).hexdigest() in checksum.read_text()
    with ZipFile(archive) as bundle:
        names = bundle.namelist()
        expected = {
            "MQL5/Experts/AnchorRisk/" + p.relative_to(ROOT / "mt5").as_posix()
            for p in (ROOT / "mt5").rglob("*")
            if p.suffix in (".mq5", ".mqh") and p.name != "LocalRiskPanel.mq5"
        }
        assert expected.issubset(names)
        assert not any(name.endswith("LocalRiskPanel.mq5") for name in names)
        assert {"LICENSE", "README.txt", "INSTALLATION.md", "DEMO-CHECKLIST.md"}.issubset(names)
        assert not any(name.endswith((".ex5", ".env", ".json", ".log")) for name in names)
        assert all(not name.startswith("/") and ".." not in name.split("/") for name in names)
        assert "SOURCE, not a precompiled .ex5" in bundle.read("README.txt").decode()


def test_local_panel_archive_is_separate_reproducible_and_source_only(tmp_path):
    archive, checksum = package_local_panel(tmp_path / "first")
    other, _ = package_local_panel(tmp_path / "second")
    assert archive.read_bytes() == other.read_bytes()
    assert hashlib.sha256(archive.read_bytes()).hexdigest() in checksum.read_text()
    with ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert "MQL5/Experts/AnchorLocal/LocalRiskPanel.mq5" in names
        assert "MQL5/Experts/AnchorLocal/BreakEvenAgent.mq5" not in names
        assert {
            f"MQL5/Experts/AnchorLocal/Include/RiskAgent/{filename}" for filename in INCLUDES
        }.issubset(names)
        assert {"LICENSE", "README.txt", "LOCAL-PANEL.md"}.issubset(names)
        assert not any(name.endswith((".ex5", ".env", ".json", ".log")) for name in names)
        assert all(not name.startswith("/") and ".." not in name.split("/") for name in names)
        assert "does not use Telegram" in bundle.read("README.txt").decode()
        source = bundle.read("MQL5/Experts/AnchorLocal/LocalRiskPanel.mq5").decode()
        assert "void OnChartEvent" in source
        assert "ExecutionEnabled=false" in source
        assert "AllowLiveAccount=false" in source
        assert "BuildResult(command,current" in source
        assert "WebRequest" not in source and "/v1/" not in source
