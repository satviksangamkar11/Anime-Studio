"""Ordered H3 pipeline plan (pure, no I/O). The UI shows it; render_controller.plan_pipeline fills the results.

A step result is {"ok": bool, "reasons": [str], "details": {...}}. A missing result = pending.
Assembly is allowed only when every PRE_ASSEMBLY step is ready. The loudness check runs after the AAC export,
so it never blocks assembly.
"""

STEP_ORDER = (
    ("lint", "Lint the shot rows (linter, profile, paths)"),
    ("route", "Route each shot to an H3 mode (5-mode router)"),
    ("prompt", "Compile each shot prompt"),
    ("manifest", "Asset manifest: hashes current, no missing or placeholder clips"),
    ("fallback", "Fallback ladder: no shot waits at the human gate"),
    ("render", "H3 render results exist for every shot"),
    ("step9_qc", "Step 9 final QC (SFX, continuity, closing payoff, labels)"),
    ("gate_d", "Gate D audio plan for every selected language"),
    ("assembly", "Assembly (one reel per language)"),
    ("loudness", "Post-AAC loudness check (-14 LUFS, TP <= -1.5 dBTP)"),
)
PRE_ASSEMBLY = ("lint", "route", "prompt", "manifest", "fallback", "render", "step9_qc", "gate_d")
POST_ASSEMBLY = ("loudness",)
READY, BLOCKED, PENDING = "ready", "blocked", "pending"


def _step(sid, label, status, reasons, details=None):
    return {"id": sid, "label": label, "status": status, "reasons": list(reasons), "details": dict(details or {})}


def build_plan(results):
    """results: {step_id: {"ok": bool, "reasons": [...], "details": {...}}}. Returns the ordered list of steps."""
    unknown = set(results) - {sid for sid, _ in STEP_ORDER}
    if unknown:
        raise ValueError(f"unknown pipeline step(s): {sorted(unknown)}")
    steps, status = [], {}
    for sid, label in STEP_ORDER:
        if sid == "assembly":
            blockers = [s for s in PRE_ASSEMBLY if status[s] == BLOCKED]
            waits = [s for s in PRE_ASSEMBLY if status[s] == PENDING]
            if blockers:
                st, reasons = BLOCKED, [f"{s}: {r}" for s in blockers for r in steps_reasons(steps, s)]
            elif waits:
                st, reasons = PENDING, [f"waits for {s}" for s in waits]
            else:
                st, reasons = READY, []
            steps.append(_step(sid, label, st, reasons))
            status[sid] = st
            continue
        res = results.get(sid)
        if res is None:
            st, reasons, details = PENDING, [f"not run yet"], {}
        else:
            details = res.get("details", {})
            if res.get("ok"):
                st, reasons = READY, []
            else:
                st, reasons = BLOCKED, list(res.get("reasons") or ["failed without a reason"])
        steps.append(_step(sid, label, st, reasons, details))
        status[sid] = st
    return steps


def steps_reasons(steps, sid):
    return next(s["reasons"] for s in steps if s["id"] == sid)


def assembly_allowed(steps):
    """True only when the assembly step is ready (all PRE_ASSEMBLY gates passed)."""
    return any(s["id"] == "assembly" and s["status"] == READY for s in steps)
