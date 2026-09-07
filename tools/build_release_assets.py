#!/usr/bin/env python3
"""Build and verify deterministic release assets."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "dist" / "release"
PROJECT = "binary-covering-sequence-12-3"
VERSION_RE = re.compile(r"^version:\s*[\"']?([^\"' \n]+)", re.MULTILINE)
CHECKSUM_RE = re.compile(r"^([0-9a-f]{64})  ([A-Za-z0-9_.-]+)$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def project_version() -> str:
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if match is None:
        raise ValueError("CITATION.cff has no version")
    return match.group(1).removeprefix("v")


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    files = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"tracked path is not a regular file: {relative}")
        files.append(relative)
    return sorted(files, key=lambda item: item.as_posix())


def normalized_tar_info(path: Path, archive_name: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(archive_name)
    stat = path.stat()
    info.size = stat.st_size
    info.mode = 0o755 if stat.st_mode & 0o111 else 0o644
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    return info


def build_source_archive(output: Path, version: str) -> None:
    prefix = f"{PROJECT}-v{version}"
    with output.open("wb") as raw_stream:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_stream,
            mtime=0,
        ) as gzip_stream:
            with tarfile.open(
                fileobj=gzip_stream,
                mode="w",
                format=tarfile.PAX_FORMAT,
            ) as archive:
                for relative in tracked_files():
                    source = ROOT / relative
                    archive_name = f"{prefix}/{relative.as_posix()}"
                    info = normalized_tar_info(source, archive_name)
                    with source.open("rb") as stream:
                        archive.addfile(info, stream)


def metadata_binary_hash(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="ascii"))
    value = payload.get("binary_sha256")
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"invalid binary hash in {path.relative_to(ROOT)}")
    return value


def copy_checked_binary(source: Path, destination: Path, expected: str) -> None:
    observed = sha256(source)
    if observed != expected:
        raise ValueError(
            f"{source.relative_to(ROOT)} has SHA-256 {observed}, expected {expected}"
        )
    shutil.copyfile(source, destination)
    destination.chmod(0o755)


def replace_file(source: Path, destination: Path, mode: int = 0o644) -> None:
    shutil.copyfile(source, destination)
    destination.chmod(mode)


def asset_names(version: str) -> dict[str, str]:
    return {
        "paper": f"{PROJECT}-paper-v{version}.pdf",
        "source": f"{PROJECT}-source-v{version}.tar.gz",
        "cpp": f"{PROJECT}-cpp-exhaustive-macos-arm64",
        "rust": f"{PROJECT}-rust-exhaustive-macos-arm64",
    }


def write_checksums(directory: Path, names: dict[str, str]) -> None:
    lines = [
        f"{sha256(directory / name)}  {name}\n"
        for name in sorted(names.values())
    ]
    with (directory / "SHA256SUMS").open(
        "w",
        encoding="ascii",
        newline="\n",
    ) as stream:
        stream.write("".join(lines))


def build_assets() -> None:
    version = project_version()
    names = asset_names(version)
    paper = ROOT / "build" / "paper" / "main.pdf"
    cpp_binary = ROOT / "build" / "exhaustive"
    rust_binary = (
        ROOT
        / "rust-exhaustive"
        / "target"
        / "release"
        / "binary-covering-sequence-exhaustive"
    )
    required = (paper, cpp_binary, rust_binary)
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise ValueError(
            "missing release inputs: "
            + ", ".join(str(path.relative_to(ROOT)) for path in missing)
        )

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="release-assets-",
        dir=RELEASE_DIR,
    ) as staging_text:
        staging = Path(staging_text)
        replace_file(paper, staging / names["paper"])
        build_source_archive(staging / names["source"], version)
        copy_checked_binary(
            cpp_binary,
            staging / names["cpp"],
            metadata_binary_hash(ROOT / "evidence" / "cpp-exhaustive-1-35.json"),
        )
        copy_checked_binary(
            rust_binary,
            staging / names["rust"],
            metadata_binary_hash(
                ROOT / "evidence" / "rust-exhaustive-1-35.metadata.json"
            ),
        )
        write_checksums(staging, names)

        for name in [*names.values(), "SHA256SUMS"]:
            os.replace(staging / name, RELEASE_DIR / name)

    print(f"built {len(names) + 1} release assets in {RELEASE_DIR.relative_to(ROOT)}")


def read_checksums(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="ascii").splitlines(),
        start=1,
    ):
        match = CHECKSUM_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid checksum line {line_number}")
        digest, name = match.groups()
        if name in entries:
            raise ValueError(f"duplicate checksum entry: {name}")
        entries[name] = digest
    return entries


def verify_source_archive(path: Path, version: str) -> None:
    prefix = f"{PROJECT}-v{version}/"
    expected = {f"{prefix}{item.as_posix()}" for item in tracked_files()}
    with tarfile.open(path, mode="r:gz") as archive:
        members = archive.getmembers()
        names = {member.name for member in members}
        if any(
            not member.isfile()
            or not member.name.startswith(prefix)
            or ".." in Path(member.name).parts
            for member in members
        ):
            raise ValueError("source archive contains an unsafe member")
    if names != expected:
        missing = sorted(expected - names)
        extra = sorted(names - expected)
        raise ValueError(
            f"source archive mismatch: missing={missing[:3]}, extra={extra[:3]}"
        )


def verify_assets() -> None:
    version = project_version()
    names = asset_names(version)
    checksum_path = RELEASE_DIR / "SHA256SUMS"
    if not checksum_path.is_file():
        raise ValueError("dist/release/SHA256SUMS is missing")
    entries = read_checksums(checksum_path)
    expected_names = set(names.values())
    if set(entries) != expected_names:
        raise ValueError("SHA256SUMS does not list the expected release assets")
    for name, expected in entries.items():
        path = RELEASE_DIR / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"release asset is missing or not regular: {name}")
        observed = sha256(path)
        if observed != expected:
            raise ValueError(f"release asset hash mismatch: {name}")

    cpp_expected = metadata_binary_hash(
        ROOT / "evidence" / "cpp-exhaustive-1-35.json"
    )
    rust_expected = metadata_binary_hash(
        ROOT / "evidence" / "rust-exhaustive-1-35.metadata.json"
    )
    if entries[names["cpp"]] != cpp_expected:
        raise ValueError("C++ release asset does not match retained metadata")
    if entries[names["rust"]] != rust_expected:
        raise ValueError("Rust release asset does not match retained metadata")
    verify_source_archive(RELEASE_DIR / names["source"], version)
    print(f"verified {len(entries)} release assets")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify existing release assets without rebuilding them",
    )
    arguments = parser.parse_args()
    try:
        if arguments.check:
            verify_assets()
        else:
            build_assets()
            verify_assets()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"release asset error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
