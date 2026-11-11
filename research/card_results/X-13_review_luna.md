`main` does not enforce the card’s execute requirement when assembly is blocked. It checks `pre_render_ready(gates["steps"])` instead:

> `if not pre_render_ready(gates["steps"]):`

The card requires execute to return 1 when `assembly_allowed` is false. Check `if not gates["assembly_allowed"]:` here and return 1 before `prepare` or writing `render_ready.json`.

VERDICT: FIX-FIRST.