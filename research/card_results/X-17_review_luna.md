`check_free_disk(out / "export")` runs once before the language loop, so later exports can proceed after earlier exports have reduced free space below the minimum. Move the check to immediately before each `subprocess.run(argv_, ...)` export.

VERDICT: FIX-FIRST