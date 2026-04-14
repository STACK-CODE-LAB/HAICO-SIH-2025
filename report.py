"""
report.py
"""

from __future__ import annotations


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def build(
    ai_result: dict,
    obfu_result: dict,
    original_filename: str,
    passes_used: str,
) -> dict:

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

    report["ai"] = {
        "original_source": ai_result.get("original_source", ""),
        "enhanced_source": ai_result.get("enhanced_source", ""),
        "error":           ai_result.get("error"),
    }

    if obfu_result.get("error"):
        report["error"]          = obfu_result["error"]
        report["verdict"]        = "ERROR"
        report["verdict_detail"] = "Pipeline failed — see error details."
        return report

    match = obfu_result.get("outputs_match", False)
    report["outputs"] = {
        "plain":      obfu_result.get("plain_output", ""),
        "obfuscated": obfu_result.get("obfu_output", ""),
        "match":      match,
    }

    raw = obfu_result.get("metrics", {})
    pm  = raw.get("plain", {})
    om  = raw.get("obfuscated", {})

    def safe_ratio(a, b) -> str:
        try:
            if a and b:
                return f"{b / a:.2f}x"
        except Exception:
            pass
        return "n/a"

    report["metrics"] = {
        "plain": {
            "size_bytes":      pm.get("size_bytes", 0),
            "size_human":      _fmt_bytes(pm.get("size_bytes", 0)),
            "instructions":    pm.get("instructions", -1),
            "functions":       pm.get("functions", -1),
            "branches":        pm.get("branches", -1),
            "strings_visible": pm.get("strings_visible"),
            "sections":        pm.get("sections", {}),
        },
        "obfuscated": {
            "size_bytes":      om.get("size_bytes", 0),
            "size_human":      _fmt_bytes(om.get("size_bytes", 0)),
            "instructions":    om.get("instructions", -1),
            "functions":       om.get("functions", -1),
            "branches":        om.get("branches", -1),
            "strings_visible": om.get("strings_visible"),
            "sections":        om.get("sections", {}),
        },
        "ratios": {
            "size":         safe_ratio(pm.get("size_bytes"),   om.get("size_bytes")),
            "instructions": safe_ratio(pm.get("instructions"), om.get("instructions")),
            "branches":     safe_ratio(pm.get("branches"),     om.get("branches")),
        },
    }

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