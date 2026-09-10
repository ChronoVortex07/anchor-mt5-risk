"""Build a reproducible source-only MT5 installation ZIP, excluding all credentials."""

import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
INSTALL = """Anchor MT5 EA — source prerelease

This archive contains SOURCE, not a precompiled .ex5. MetaEditor compilation and
broker demo testing have not been performed by the release publisher.

1. In MT5: File > Open Data Folder. Close any running Anchor EA before upgrading.
2. Copy this archive's MQL5 folder into that data folder, merging the folders.
3. Open MQL5/Experts/AnchorRisk/BreakEvenAgent.mq5 in MetaEditor; press F7.
4. Add your service's HTTPS URL in Tools > Options > Expert Advisors > WebRequest.
5. Open your service operator's Telegram bot and send /link.
6. Attach AnchorRisk/BreakEvenAgent to one chart. Set ApiUrl and PairingCode.
   Keep ExecutionEnabled=false. Broker credentials stay exclusively in MT5.
7. Follow INSTALLATION.md and DEMO-CHECKLIST.md before enabling demo execution.

No official hosted bot is embedded in this archive. Use the bot/API URL supplied
by your service operator, or follow the repository's Telegram setup guide.

Project: https://github.com/ChronoVortex07/anchor-mt5-risk
License: MIT; see LICENSE. Never delete unresolved execution journals to retry.
"""


def package(output: Path, root: Path = ROOT) -> tuple[Path, Path]:
    required = root / "mt5/BreakEvenAgent.mq5"
    if not required.is_file() or not (root / "LICENSE").is_file():
        raise ValueError("Run from a complete source checkout with its license")
    entries = {"README.txt": INSTALL.encode(), "LICENSE": (root / "LICENSE").read_bytes()}
    for source in sorted((root / "mt5").rglob("*")):
        if source.is_file() and not source.is_symlink() and source.suffix in (".mq5", ".mqh"):
            name = "MQL5/Experts/AnchorRisk/" + source.relative_to(root / "mt5").as_posix()
            entries[name] = source.read_bytes()
    entries["INSTALLATION.md"] = (root / "docs/mt5-installation.md").read_bytes()
    entries["DEMO-CHECKLIST.md"] = (root / "docs/demo-checklist.md").read_bytes()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / "anchor-mt5-ea-source.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for name, data in sorted(entries.items()):
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data)
    checksum = output / "SHA256SUMS.txt"
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
