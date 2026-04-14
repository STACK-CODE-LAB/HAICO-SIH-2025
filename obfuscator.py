"""
obfuscator.py
=============
Compiles a C/C++ source file twice:
  - plain   : no obfuscation
  - obfuscated : Polaris passes enabled

Returns a dict with:
  - outputs_match  : bool
  - plain_output   : str
  - obfu_output    : str
  - metrics        : dict  (sizes, instruction counts, entropy, …)
  - plain_bin      : str   (path to plain binary)
  - obfu_bin       : str   (path to obfuscated binary)
  - error          : str | None
"""

import collections
import math
import os
import subprocess
from pathlib import Path

import config


def _run(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        timeout=config.JOB_TIMEOUT
    )


def _count_insns(binary: str) -> int:
    r = _run(f"objdump -d {binary} 2>/dev/null | grep -c '^\\s*[0-9a-f]*:'")
    try:
        return int(r.stdout.strip())
    except Exception:
        return -1


def _count_fns(binary: str) -> int:
    r = _run(f"nm -U {binary} 2>/dev/null | grep -c ' T '")
    try:
        return int(r.stdout.strip())
    except Exception:
        return -1


def _count_branches(binary: str) -> int:
    r = _run(
        f"objdump -d {binary} 2>/dev/null "
        r"| grep -Ec '\bj[a-z]{1,3}\b|\bcall\b'"
    )
    try:
        return int(r.stdout.strip())
    except Exception:
        return -1


def _entropy(binary: str) -> float | None:
    r = _run(f"objdump -s -j .text {binary} 2>/dev/null")
    if r.returncode != 0:
        return None
    hb: list[int] = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and len(parts[0]) > 4:
            for w in parts[1:5]:
                for i in range(0, len(w), 2):
                    try:
                        hb.append(int(w[i:i + 2], 16))
                    except ValueError:
                        pass
    if not hb:
        return None
    freq = collections.Counter(hb)
    total = len(hb)
    ent = -sum((c / total) * math.log2(c / total) for c in freq.values())
    return round(ent, 3)


def _str_visible(binary: str, needle: str) -> bool:
    r = _run(f"strings {binary} 2>/dev/null | grep -qF '{needle}'")
    return r.returncode == 0


def _section_sizes(binary: str) -> dict[str, int]:
    r = _run(f"size -A {binary} 2>/dev/null")
    sizes: dict[str, int] = {}
    for line in r.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            try:
                sizes[parts[0]] = int(parts[1])
            except ValueError:
                pass
    return sizes


def _collect_metrics(binary: str) -> dict:
    return {
        "size_bytes":   os.path.getsize(binary),
        "instructions": _count_insns(binary),
        "functions":    _count_fns(binary),
        "branches":     _count_branches(binary),
        "entropy":      _entropy(binary),
        "sections":     _section_sizes(binary),
    }


def run_pipeline(src: str, job_dir: str, passes: str = "") -> dict:
    """
    Parameters
    ----------
    src      : absolute path to the (AI-enhanced) source file
    job_dir  : working directory for this job's binaries
    passes   : comma-separated Polaris pass names, e.g. "fla,gvenc,sub"
               Falls back to config.DEFAULT_PASSES if empty.

    Returns
    -------
    dict with keys: outputs_match, plain_output, obfu_output,
                    metrics, plain_bin, obfu_bin, error
    """
    passes    = passes.strip() or config.DEFAULT_PASSES
    clang     = config.POLARIS_CLANG
    flags     = config.COMPILE_FLAGS
    plain_bin = str(Path(job_dir) / "plain_out")
    obfu_bin  = str(Path(job_dir) / "obfu_out")

    result: dict = {
        "outputs_match": False,
        "plain_output":  "",
        "obfu_output":   "",
        "metrics":       {},
        "plain_bin":     plain_bin,
        "obfu_bin":      obfu_bin,
        "error":         None,
    }

    # ── compile plain ─────────────────────────────────────────────────────────
    cmd_plain = f"{clang} {src} {flags} -o {plain_bin}"
    r = _run(cmd_plain)
    if r.returncode != 0:
        result["error"] = f"Plain compilation failed:\n{r.stderr}"
        return result

    # ── compile obfuscated ────────────────────────────────────────────────────
    cmd_obfu = f"{clang} {src} {flags} -mllvm -passes={passes} -o {obfu_bin}"
    r = _run(cmd_obfu)
    if r.returncode != 0:
        result["error"] = f"Obfuscated compilation failed:\n{r.stderr}"
        return result

    # ── run both ──────────────────────────────────────────────────────────────
    rp = _run(plain_bin)
    ro = _run(obfu_bin)
    result["plain_output"] = rp.stdout
    result["obfu_output"]  = ro.stdout
    result["outputs_match"] = rp.stdout.strip() == ro.stdout.strip()

    # ── metrics ───────────────────────────────────────────────────────────────
    pm = _collect_metrics(plain_bin)
    om = _collect_metrics(obfu_bin)

    # string-visibility check — look for a short unique token from the source
    # We check for the literal string "main" as a proxy; gvenc hides string consts
    pm["strings_visible"] = _str_visible(plain_bin, "main")
    om["strings_visible"] = _str_visible(obfu_bin, "main")

    size_ratio = (om["size_bytes"] / pm["size_bytes"]
                  if pm["size_bytes"] else 0)

    result["metrics"] = {
        "plain":       pm,
        "obfuscated":  om,
        "size_ratio":  round(size_ratio, 2),
        "insn_ratio":  round(om["instructions"] / pm["instructions"], 2)
                       if pm["instructions"] > 0 else 0,
        "passes_used": passes,
    }

    return result