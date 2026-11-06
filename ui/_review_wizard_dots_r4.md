

FINAL:
- high, pipeline.py:406, A rejected gate must stay rejected and be decidable again regardless of stage status; currently the gate state becomes "locked" when the stage is partially re-run (status "ready"), preventing further decisions. Fix: change `elif latest[g] == "reject" and stage_status == "rejected":` to `elif latest[g] == "reject":`.