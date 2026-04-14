"""
ai_enhancer.py
==============
Sends raw C/C++ source to Gemini and gets back:
  - Polaris __attribute__((annotate(...))) on every non-trivial function
  - asm("backend-obfu") in main
  - Junk loops / opaque arithmetic inserted in function bodies
  - Semantics preserved exactly (same stdout as original)

Returns
-------
  enhanced_source : str   — modified C/C++ source ready for Polaris clang
  ai_diff         : dict  — {"original": str, "enhanced": str}  for the UI
  error           : str | None
"""

import os
import google.generativeai as genai
import config

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM = """\
You are a C/C++ obfuscation assistant working with the Polaris LLVM obfuscator.
Your job is to modify source code so that:

1. POLARIS ANNOTATIONS
   Add  __attribute__((annotate("PASSES")))  before every non-trivial function
   (not main). Choose annotations from:
     flattening      - for loop-heavy or branch-heavy functions
     boguscfg        - for arithmetic-heavy functions
     substitution    - for any function with arithmetic operations
     aliasaccess     - for functions that access local variables heavily
     indirectcall    - for functions that call other functions
     indirectbr      - for functions with complex branching
     linearmba       - for functions with bitwise operations
   You can combine multiple: annotate("flattening,substitution,boguscfg")

2. BACKEND OBFUSCATION MARKER
   Inside main(), add this as the very first statement:
     asm("backend-obfu");

3. JUNK LOOPS  (logic obfuscation)
   Inside each non-trivial function body, insert 1-2 junk computation blocks
   that look real but have no effect on output. Rules:
   - Use a  volatile int _sink = 0;  variable to prevent compiler elimination
   - Perform dead arithmetic on local variables or constants
   - Use short loops (3-7 iterations) with opaque conditions
   - Place them BEFORE the real logic so they look like initialization
   Example junk block:
     volatile int _sink = 0;
     for (int _j = 0; _j < 3; _j++) { _sink ^= (_j * 0x5A5A + 1); }

4. STRICT RULES
   - Do NOT change the program's observable output (stdout must be identical)
   - Do NOT add/remove #include directives unless needed for the junk code
   - Do NOT rename functions or variables
   - Do NOT add a main() if one does not exist
   - Return ONLY the raw C/C++ source code — no markdown, no explanation
"""


def enhance(source: str, filename: str) -> dict:
    """
    Parameters
    ----------
    source   : raw source code string
    filename : original filename (used to hint language: .c vs .cpp)

    Returns
    -------
    {
      "enhanced_source": str,
      "original_source": str,
      "error": str | None
    }
    """
    result = {
        "enhanced_source": source,   # fallback = unchanged
        "original_source": source,
        "error": None,
    }

    api_key = config.GEMINI_API_KEY
    if not api_key:
        result["error"] = "GEMINI_API_KEY not set in environment"
        return result

    lang_hint = "C++" if filename.endswith(".cpp") else "C"
    user_msg  = (
        f"Enhance the following {lang_hint} source file named '{filename}' "
        f"according to your instructions.\n\n"
        f"```\n{source}\n```"
    )

    try:
        genai.configure(api_key=api_key)
        model    = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            system_instruction=_SYSTEM,
        )
        response = model.generate_content(user_msg)
        text     = response.text.strip()

        # Strip accidental markdown fences if Gemini adds them
        if text.startswith("```"):
            lines = text.splitlines()
            # Remove first fence line (```c / ```cpp / ```)
            lines = lines[1:]
            # Remove last fence if present
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)

        result["enhanced_source"] = text

    except Exception as exc:
        result["error"] = f"Gemini API error: {exc}"

    return result