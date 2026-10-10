"""Small Windows DPAPI secret store for local operator-mediated credentials."""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import tempfile
from pathlib import Path


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _protect(data: bytes, *, decrypt: bool) -> bytes:
    if os.name != "nt":
        raise OSError("Windows DPAPI is unavailable")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_Blob), ctypes.c_wchar_p, ctypes.POINTER(_Blob), ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(_Blob),
    ]
    crypt32.CryptProtectData.restype = ctypes.c_int
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_Blob), ctypes.POINTER(ctypes.c_wchar_p), ctypes.POINTER(_Blob), ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(_Blob),
    ]
    crypt32.CryptUnprotectData.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    source_buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = _Blob(len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = _Blob()
    if decrypt:
        ok = crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = crypt32.CryptProtectData(ctypes.byref(source), "RetainIQ local reader token", None, None, None, 1,
                                      ctypes.byref(target))
    if not ok:
        raise OSError("Windows DPAPI operation failed")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)


def store_dpapi_secret(path: str | Path, secret: str) -> None:
    """Atomically store a UTF-8 secret protected to the current Windows user."""
    target = Path(path).expanduser().resolve()
    if not secret or "\x00" in secret:
        raise ValueError("invalid secret")
    target.parent.mkdir(parents=True, exist_ok=True)
    encrypted = b"RIQDPAPI1" + _protect(secret.encode("utf-8"), decrypt=False)
    fd, temporary_name = tempfile.mkstemp(prefix=".riq-secret-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encrypted)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, target)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def load_dpapi_secret(path: str | Path) -> str:
    data = Path(path).expanduser().read_bytes()
    if not data.startswith(b"RIQDPAPI1"):
        raise ValueError("protected secret file has an unsupported format")
    secret = _protect(data[len(b"RIQDPAPI1"):], decrypt=True).decode("utf-8")
    if not secret or "\x00" in secret:
        raise ValueError("protected secret file is invalid")
    return secret


def _run_with_secret(secret_file: Path, command: list[str]) -> int:
    if not command:
        raise ValueError("a child command is required")
    environment = os.environ.copy()
    environment["RETAINIQ_MODEL_TOKEN"] = load_dpapi_secret(secret_file)
    return subprocess.run(command, env=environment, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m retaniq.secret_store")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run a child process with a DPAPI-protected reader token")
    run.add_argument("--file", type=Path, required=True)
    run.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        return _run_with_secret(args.file, command)
    except (OSError, ValueError) as exc:
        print(f"secret-store error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
