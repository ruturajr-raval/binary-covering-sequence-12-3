#!/usr/bin/env python3
"""Build and verify release assets against an immutable Git tree."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
RELEASE_DIR = DIST_DIR / "release"
PROJECT = "binary-covering-sequence-12-3"
VERSION_RE = re.compile(r"^version:\s*[\"']?([^\"' \n]+)", re.MULTILINE)
CHECKSUM_RE = re.compile(r"^([0-9a-f]{64})  ([A-Za-z0-9_.-]+)$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class TreeEntry:
    path: str
    mode: int
    object_id: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(arguments: list[str]) -> bytes:
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def resolve_ref(reference: str) -> str:
    commit = git_output(
        ["rev-parse", "--verify", f"{reference}^{{commit}}"]
    ).decode("ascii").strip()
    if COMMIT_RE.fullmatch(commit) is None:
        raise ValueError(f"Git reference did not resolve to a commit: {reference}")
    return commit


def tree_entries(reference: str) -> list[TreeEntry]:
    commit = resolve_ref(reference)
    entries = []
    for record in git_output(["ls-tree", "-r", "-z", commit]).split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode_text, object_type, object_id = metadata.decode("ascii").split()
        path = os.fsdecode(raw_path)
        parts = Path(path).parts
        if (
            object_type != "blob"
            or mode_text not in {"100644", "100755"}
            or Path(path).is_absolute()
            or ".." in parts
        ):
            raise ValueError(f"unsupported Git tree entry: {path}")
        entries.append(
            TreeEntry(
                path=path,
                mode=0o755 if mode_text == "100755" else 0o644,
                object_id=object_id,
            )
        )
    return sorted(entries, key=lambda entry: entry.path)


def blob_bytes(object_id: str) -> bytes:
    return git_output(["cat-file", "blob", object_id])


def entry_by_path(reference: str, relative: str) -> TreeEntry:
    for entry in tree_entries(reference):
        if entry.path == relative:
            return entry
    raise ValueError(f"{relative} is absent from Git reference {reference}")


def text_at_ref(reference: str, relative: str, encoding: str) -> str:
    entry = entry_by_path(reference, relative)
    return blob_bytes(entry.object_id).decode(encoding)


def project_version(reference: str = "HEAD") -> str:
    text = text_at_ref(reference, "CITATION.cff", "utf-8")
    match = VERSION_RE.search(text)
    if match is None:
        raise ValueError("CITATION.cff has no version")
    return match.group(1).removeprefix("v")


def validate_tag(reference: str, tag: str, version: str) -> str:
    if tag != f"v{version}":
        raise ValueError(f"release tag {tag!r} does not match version {version}")
    commit = resolve_ref(reference)
    tag_commit = resolve_ref(f"refs/tags/{tag}")
    if tag_commit != commit:
        raise ValueError(
            f"release tag {tag} resolves to {tag_commit}, expected {commit}"
        )
    return commit


def normalized_tar_info(
    data: bytes,
    mode: int,
    archive_name: str,
) -> tarfile.TarInfo:
    info = tarfile.TarInfo(archive_name)
    info.size = len(data)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    return info


def build_source_archive(
    output: Path,
    version: str,
    reference: str,
) -> None:
    commit = resolve_ref(reference)
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
                for entry in tree_entries(commit):
                    data = blob_bytes(entry.object_id)
                    archive_name = f"{prefix}/{entry.path}"
                    archive.addfile(
                        normalized_tar_info(data, entry.mode, archive_name),
                        io.BytesIO(data),
                    )


def metadata_binary_hash(relative: str, reference: str) -> str:
    payload = json.loads(text_at_ref(reference, relative, "ascii"))
    value = payload.get("binary_sha256")
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"invalid binary hash in {relative}")
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


def verify_pdf(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{path} is missing or unsafe")
    if path.read_bytes()[:5] != b"%PDF-":
        raise ValueError(f"{path} is not a PDF")


def verify_paper_binding(release_paper: Path, expected_paper: Path) -> None:
    verify_pdf(release_paper)
    verify_pdf(expected_paper)
    if sha256(release_paper) != sha256(expected_paper):
        raise ValueError("release paper does not match the tagged-source build")


def asset_names(version: str) -> dict[str, str]:
    return {
        "paper": f"{PROJECT}-paper-v{version}.pdf",
        "source": f"{PROJECT}-source-v{version}.tar.gz",
        "cpp": f"{PROJECT}-cpp-exhaustive-v{version}-macos-arm64",
        "rust": f"{PROJECT}-rust-exhaustive-v{version}-macos-arm64",
    }


def expected_release_files(reference: str) -> set[str]:
    version = project_version(reference)
    return set(asset_names(version).values()) | {"SHA256SUMS"}


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


def build_assets(reference: str, tag: str | None = None) -> None:
    commit = resolve_ref(reference)
    version = project_version(commit)
    if tag is not None:
        validate_tag(commit, tag, version)
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
    verify_pdf(paper)

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix="release-assets-", dir=DIST_DIR)
    )
    try:
        replace_file(paper, staging / names["paper"])
        build_source_archive(staging / names["source"], version, commit)
        copy_checked_binary(
            cpp_binary,
            staging / names["cpp"],
            metadata_binary_hash(
                "evidence/cpp-exhaustive-1-35.json",
                commit,
            ),
        )
        copy_checked_binary(
            rust_binary,
            staging / names["rust"],
            metadata_binary_hash(
                "evidence/rust-exhaustive-1-35.metadata.json",
                commit,
            ),
        )
        write_checksums(staging, names)

        if RELEASE_DIR.is_symlink():
            raise ValueError("dist/release must not be a symlink")
        if RELEASE_DIR.exists():
            shutil.rmtree(RELEASE_DIR)
        os.replace(staging, RELEASE_DIR)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    print(
        f"built {len(names) + 1} release assets from {commit} "
        f"in {RELEASE_DIR.relative_to(ROOT)}"
    )


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


def validate_remote_release_payload(
    payload: dict,
    tag: str,
    expected_files: set[str],
    state: str,
    local_directory: Path | None = None,
    require_immutable: bool = False,
) -> None:
    if payload.get("tagName") != tag:
        raise ValueError("remote release tag does not match")
    expected_draft = state == "draft"
    if payload.get("isDraft") is not expected_draft:
        raise ValueError(f"remote release is not in the expected {state} state")
    if require_immutable and payload.get("isImmutable") is not True:
        raise ValueError("published release is not immutable")

    raw_assets = payload.get("assets")
    if not isinstance(raw_assets, list):
        raise ValueError("remote release assets are missing")
    assets: dict[str, dict] = {}
    for asset in raw_assets:
        if not isinstance(asset, dict):
            raise ValueError("remote release asset record is invalid")
        name = asset.get("name")
        if not isinstance(name, str) or name in assets:
            raise ValueError("remote release asset names are invalid")
        assets[name] = asset
    if set(assets) != expected_files:
        raise ValueError("remote release does not contain the exact asset set")

    for name, asset in assets.items():
        digest = asset.get("digest")
        size = asset.get("size")
        if asset.get("state") != "uploaded":
            raise ValueError(f"remote release asset is not uploaded: {name}")
        if (
            not isinstance(digest, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
        ):
            raise ValueError(f"remote release asset has no SHA-256 digest: {name}")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError(f"remote release asset has invalid size: {name}")

    if local_directory is None:
        return
    if not local_directory.is_dir() or local_directory.is_symlink():
        raise ValueError("local release directory is missing or unsafe")
    local_paths = list(local_directory.iterdir())
    if (
        {path.name for path in local_paths} != expected_files
        or any(not path.is_file() or path.is_symlink() for path in local_paths)
    ):
        raise ValueError("local release directory does not match the asset set")
    for name, asset in assets.items():
        path = local_directory / name
        if asset["digest"] != f"sha256:{sha256(path)}":
            raise ValueError(f"remote release asset digest mismatch: {name}")
        if asset["size"] != path.stat().st_size:
            raise ValueError(f"remote release asset size mismatch: {name}")


def check_remote_release(
    repository: str,
    reference: str,
    tag: str,
    state: str,
    compare_local: bool,
    require_immutable: bool,
) -> None:
    commit = resolve_ref(reference)
    version = project_version(commit)
    validate_tag(commit, tag, version)
    output = subprocess.run(
        [
            "gh",
            "release",
            "view",
            tag,
            "--repo",
            repository,
            "--json",
            "tagName,isDraft,isImmutable,assets",
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout
    payload = json.loads(output)
    validate_remote_release_payload(
        payload,
        tag,
        expected_release_files(commit),
        state,
        RELEASE_DIR if compare_local else None,
        require_immutable,
    )
    print(f"verified remote {state} release {tag} against {commit}")


def verify_source_archive(
    path: Path,
    version: str,
    reference: str,
) -> None:
    commit = resolve_ref(reference)
    prefix = f"{PROJECT}-v{version}/"
    entries = tree_entries(commit)
    expected = {
        f"{prefix}{entry.path}": entry
        for entry in entries
    }
    with tarfile.open(path, mode="r:gz") as archive:
        members = archive.getmembers()
        member_names = [member.name for member in members]
        if len(member_names) != len(set(member_names)):
            raise ValueError("source archive contains duplicate members")
        observed = {member.name: member for member in members}
        if any(
            not member.isfile()
            or not member.name.startswith(prefix)
            or Path(member.name).is_absolute()
            or ".." in Path(member.name).parts
            or member.uid != 0
            or member.gid != 0
            or member.mtime != 0
            for member in members
        ):
            raise ValueError("source archive contains an unsafe member")
        if set(observed) != set(expected):
            missing = sorted(set(expected) - set(observed))
            extra = sorted(set(observed) - set(expected))
            raise ValueError(
                f"source archive mismatch: missing={missing[:3]}, extra={extra[:3]}"
            )
        for name, entry in expected.items():
            member = observed[name]
            if member.mode != entry.mode:
                raise ValueError(f"source archive mode mismatch: {name}")
            stream = archive.extractfile(member)
            if stream is None or stream.read() != blob_bytes(entry.object_id):
                raise ValueError(f"source archive content mismatch: {name}")


def verify_assets(
    reference: str,
    tag: str | None = None,
    expected_paper: Path | None = None,
) -> None:
    commit = resolve_ref(reference)
    version = project_version(commit)
    if tag is not None:
        validate_tag(commit, tag, version)
    names = asset_names(version)
    checksum_path = RELEASE_DIR / "SHA256SUMS"
    if not checksum_path.is_file() or checksum_path.is_symlink():
        raise ValueError("dist/release/SHA256SUMS is missing or unsafe")
    expected_files = set(names.values()) | {"SHA256SUMS"}
    actual_files = {
        path.name
        for path in RELEASE_DIR.iterdir()
        if path.is_file() and not path.is_symlink()
    }
    if actual_files != expected_files or any(
        not path.is_file() or path.is_symlink()
        for path in RELEASE_DIR.iterdir()
    ):
        raise ValueError("dist/release contains unexpected or unsafe files")

    entries = read_checksums(checksum_path)
    expected_names = set(names.values())
    if set(entries) != expected_names:
        raise ValueError("SHA256SUMS does not list the expected release assets")
    for name, expected in entries.items():
        observed = sha256(RELEASE_DIR / name)
        if observed != expected:
            raise ValueError(f"release asset hash mismatch: {name}")

    cpp_expected = metadata_binary_hash(
        "evidence/cpp-exhaustive-1-35.json",
        commit,
    )
    rust_expected = metadata_binary_hash(
        "evidence/rust-exhaustive-1-35.metadata.json",
        commit,
    )
    if entries[names["cpp"]] != cpp_expected:
        raise ValueError("C++ release asset does not match retained metadata")
    if entries[names["rust"]] != rust_expected:
        raise ValueError("Rust release asset does not match retained metadata")
    paper = RELEASE_DIR / names["paper"]
    verify_pdf(paper)
    if expected_paper is not None:
        verify_paper_binding(paper, expected_paper)
    verify_source_archive(RELEASE_DIR / names["source"], version, commit)
    print(f"verified {len(entries)} release assets against {commit}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify existing release assets without rebuilding them",
    )
    parser.add_argument(
        "--ref",
        default="HEAD",
        help="Git commit or ref whose tree the source archive must match",
    )
    parser.add_argument(
        "--tag",
        help="require this version tag to resolve to the selected ref",
    )
    parser.add_argument(
        "--expected-paper",
        type=Path,
        help="require the release PDF to match this tagged-source build",
    )
    parser.add_argument(
        "--check-remote",
        action="store_true",
        help="verify the GitHub release asset set and remote digests",
    )
    parser.add_argument(
        "--repo",
        help="GitHub owner/repository for remote release verification",
    )
    parser.add_argument(
        "--remote-state",
        choices=("draft", "published"),
        help="required GitHub release state",
    )
    parser.add_argument(
        "--compare-local",
        action="store_true",
        help="compare remote asset digests with dist/release",
    )
    parser.add_argument(
        "--require-immutable",
        action="store_true",
        help="require GitHub to report the published release as immutable",
    )
    arguments = parser.parse_args()
    expected_paper = arguments.expected_paper
    if expected_paper is not None and not expected_paper.is_absolute():
        expected_paper = ROOT / expected_paper
    try:
        if arguments.check_remote:
            if (
                arguments.repo is None
                or arguments.tag is None
                or arguments.remote_state is None
            ):
                raise ValueError(
                    "--check-remote requires --repo, --tag, and --remote-state"
                )
            check_remote_release(
                arguments.repo,
                arguments.ref,
                arguments.tag,
                arguments.remote_state,
                arguments.compare_local,
                arguments.require_immutable,
            )
        elif arguments.check:
            verify_assets(arguments.ref, arguments.tag, expected_paper)
        else:
            build_assets(arguments.ref, arguments.tag)
            verify_assets(arguments.ref, arguments.tag, expected_paper)
    except (
        json.JSONDecodeError,
        OSError,
        UnicodeError,
        ValueError,
        subprocess.CalledProcessError,
        tarfile.TarError,
    ) as error:
        print(f"release asset error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
