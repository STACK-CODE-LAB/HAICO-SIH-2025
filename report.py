"""
report.py
=========
Takes the raw dicts from ai_enhancer and obfuscator and
builds a clean JSON-serialisable report dict for the frontend.
"""

from __future__ import annotations


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} GB"


def build(
    ai_result: dict,
    obfu_result: dict,
    original_filename: str,
    passes_used: str,
) -> dict:
    """
    Returns a report dict with everything the frontend needs.

    Top-level keys
    --------------
    verdict        : "PASS" | "FAIL" | "ERROR"
    verdict_detail : human-readable string
    original_filename
    passes_used
    ai             : {original_source, enhanced_source, ai_error}
    outputs        : {plain, obfuscated, match}
    metrics        : {plain: {...}, obfuscated: {...}, ratios: {...}}
    error          : str | None   (pipeline-level error)
    """

    report: dict = {
        "verdict":           "ERROR",
        "verdict_detail":    "",
        "original_filename": original_filename,
        "passes_used":       passes_used,
        "ai":                {},
        "outputs":           {},
        "metrics":           {},
        "error":             None,
    }

    # ── AI layer ──────────────────────────────────────────────────────────────
    report["ai"] = {
        "original_source": ai_result.get("original_source", ""),
        "enhanced_source": ai_result.get("enhanced_source", ""),
        "error":           ai_result.get("error"),
    }

    # ── Pipeline error (compile fail, etc.) ───────────────────────────────────
    if obfu_result.get("error"):
        report["error"]          = obfu_result["error"]
        report["verdict"]        = "ERROR"
        report["verdict_detail"] = "Pipeline failed — see error details."
        return report

    # ── Outputs ───────────────────────────────────────────────────────────────
    match = obfu_result.get("outputs_match", False)
    report["outputs"] = {
        "plain":      obfu_result.get("plain_output", ""),
        "obfuscated": obfu_result.get("obfu_output", ""),
        "match":      match,
    }

    # ── Metrics ───────────────────────────────────────────────────────────────
    raw = obfu_result.get("metrics", {})
    pm  = raw.get("plain", {})
    om  = raw.get("obfuscated", {})

    def safe_ratio(a, b) -> str:
        try:
            return f"{b / a:.2f}x"
        except Exception:
            return "n/a"

    report["metrics"] = {
        "plain": {
            "size_bytes":   pm.get("size_bytes", 0),
            "size_human":   _fmt_bytes(pm.get("size_bytes", 0)),
            "instructions": pm.get("instructions", -1),
            "functions":    pm.get("functions", -1),
            "branches":     pm.get("branches", -1),
            "entropy":      pm.get("entropy"),
            "strings_visible": pm.get("strings_visible"),
            "sections":     pm.get("sections", {}),
        },
        "obfuscated": {
            "size_bytes":   om.get("size_bytes", 0),
            "size_human":   _fmt_bytes(om.get("size_bytes", 0)),
            "instructions": om.get("instructions", -1),
            "functions":    om.get("functions", -1),
            "branches":     om.get("branches", -1),
            "entropy":      om.get("entropy"),
            "strings_visible": om.get("strings_visible"),
            "sections":     om.get("sections", {}),
        },
        "ratios": {
            "size":         safe_ratio(pm.get("size_bytes", 0),   om.get("size_bytes", 0)),
            "instructions": safe_ratio(pm.get("instructions", 0), om.get("instructions", 0)),
            "branches":     safe_ratio(pm.get("branches", 0),     om.get("branches", 0)),
            "entropy_delta": round(
                (om.get("entropy") or 0) - (pm.get("entropy") or 0), 3
            ),
        },
    }

    # ── Verdict ───────────────────────────────────────────────────────────────
    if match:
        report["verdict"]        = "PASS"
        report["verdict_detail"] = (
            "Obfuscated binary produces identical output to the plain binary. "
            "Semantics preserved."
        )
    else:
        report["verdict"]        = "FAIL"
        report["verdict_detail"] = (
            "Output mismatch detected. The obfuscation may have altered "
            "program behaviour — review the AI-enhanced source."
        )

    return report