import os
from pathlib import Path

# ── Polaris ───────────────────────────────────────────────────────────────────
POLARIS_CLANG   = os.getenv("POLARIS_CLANG",
                    str(Path.home() / "Polaris-Obfuscator/src/build/bin/clang"))
COMPILE_FLAGS   = os.getenv("COMPILE_FLAGS", "-O0")

# Default passes (can be overridden per-request)
DEFAULT_PASSES  = os.getenv("POLARIS_PASSES",
                    "fla,gvenc,indcall,indbr,alias,bcf,sub,mba")

# ── AI ────────────────────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── Flask ─────────────────────────────────────────────────────────────────────
UPLOAD_FOLDER   = os.getenv("UPLOAD_FOLDER",
                    str(Path(__file__).parent / "uploads"))
FLASK_HOST      = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT      = int(os.getenv("FLASK_PORT", 5000))
FLASK_DEBUG     = os.getenv("FLASK_DEBUG", "true").lower() == "true"

# ── Misc ──────────────────────────────────────────────────────────────────────
ALLOWED_EXTS    = {".c", ".cpp"}
JOB_TIMEOUT     = int(os.getenv("JOB_TIMEOUT", 120))   # seconds per compile