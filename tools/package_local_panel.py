"""Build a reproducible source-only ZIP for the standalone MT5 local panel."""

import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "mt5/LocalRiskPanel.mq5"
INCLUDES = (
    "Json.mqh",
    "Protocol.mqh",
    "AccountIdentity.mqh",
    "Planner.mqh",
    "Executor.mqh",
)

INSTALL = """Anchor Local Risk Panel — source preview

This is a LOCAL-ONLY MT5 Expert Advisor. It does not use Telegram, a web
service, PostgreSQL, pairing codes, API credentials, or WebRequest.

This archive contains SOURCE, not a precompiled .ex5. The publisher could not
compile it in MetaEditor or validate broker execution from this Linux host.
Use a demo hedging account first.

1. In MT5 choose File > Open Data Folder.
2. Copy this archive's MQL5 folder into that data folder, merging folders.
3. Open MQL5/Experts/AnchorLocal/LocalRiskPanel.mq5 in MetaEditor and press F7.
4. Attach AnchorLocal/LocalRiskPanel to the chart for the symbol to manage.
5. Leave ExecutionEnabled=false while inspecting previews and the interface.
6. Complete the checks in LOCAL-PANEL.md on a demo account.
7. Enable Algo Trading and set ExecutionEnabled=true only for deliberate demo
   execution. AllowLiveAccount is a separate real-money opt-in and defaults off.

Actions always target the exact current chart symbol. A preview is recalculated
before execution and expires quickly. Closing a hedge leg can increase net
directional exposure. BE stops do not guarantee profit after costs or slippage.

Project: https://github.com/ChronoVortex07/anchor-mt5-risk
License: MIT; see LICENSE.
"""


def package(output: Path, root: Path = ROOT) -> tuple[Path, Path]:
    main = root / MAIN.relative_to(ROOT)
    license_file = root / "LICENSE"
    guide = root / "docs/local-panel.md"
    if not main.is_file() or not license_file.is_file() or not guide.is_file():
        raise ValueError("Run from a complete checkout containing the local panel")

    entries = {
        "README.txt": INSTALL.encode(),
        "LICENSE": license_file.read_bytes(),
        "LOCAL-PANEL.md": guide.read_bytes(),
        "MQL5/Experts/AnchorLocal/LocalRiskPanel.mq5": main.read_bytes(),
    }
    include_root = root / "mt5/Include/RiskAgent"
    for filename in INCLUDES:
        source = include_root / filename
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Missing required local-panel include: {filename}")
        entries[f"MQL5/Experts/AnchorLocal/Include/RiskAgent/{filename}"] = source.read_bytes()

    output.mkdir(parents=True, exist_ok=True)
    archive = output / "anchor-local-risk-panel-source.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for name, data in sorted(entries.items()):
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data)

    checksum = output / "anchor-local-risk-panel-SHA256SUMS.txt"
    checksum.write_text(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")
    return archive, checksum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build")
    args = parser.parse_args()
    for path in package(args.output):
        print(path)


if __name__ == "__main__":
    main()
