# One-off: raw stems for the Ableton mix of reel 1 (no gate, no riding, no EQ chain, no sidechain),
# plus voice and policy-cleaned SFX (before the ducker) per language. Ableton does EQ/sidechain/bus.
import json, sys
from pathlib import Path
import numpy as np, soundfile as sf
sys.path.insert(0, "D:/aai work/anime_studio_merge")
from score import stem_builder as sb, sound_select as ss, reel_mixer as rm

OUT = Path(ss.EP_DIR) / "ableton_stems"
OUT.mkdir(exist_ok=True)
plan = json.load(open(Path(ss.EP_DIR) / "score_plan.json", encoding="utf-8"))
cue = json.load(open(Path(ss.EP_DIR) / "cue_sheet.json", encoding="utf-8"))
total = int(cue["total_samples"])

sb.sidechain_gain = lambda g: np.ones(g.shape[-1])  # Ableton does the sidechains
stems, _, _ = sb.build(ss.load_selection(), plan, cue, log=lambda m: None, eq_on=False, sidechain=False)
peak = max(np.abs(sum(stems.values())).max(), 1e-9)
g = 10 ** (-6 / 20) / peak  # one common gain: music sum peaks at -6 dBFS, balance between layers kept
for name, x in stems.items():
    if np.any(x):
        sf.write(OUT / f"music_{name}.wav", (x[:, :total] * g).T.astype(np.float32), sb.SR, subtype="PCM_24")
print("music gain dB", round(20 * np.log10(g), 2))

sj = json.loads(rm.SFX_JSON.read_text(encoding="utf-8"))
events = [ev for s in sj["shots"] for ev in s["events"]]
vo_report = json.loads(rm.VO_REPORT.read_text(encoding="utf-8"))
shot_start = {s["id"]: s["start_s"] for s in cue["shots"]}
stem_st = rm.fit(rm.decode_stereo(rm.STEM_MP4), total)
stem_mono = stem_st.mean(axis=1)
env_db = rm.rms_grid_db(stem_mono)
band_st = rm.band_filter(stem_st)
for lang in rm.LANGS:
    speech = [tuple(w) for w in cue["voice"]["per_language"][lang]]
    vo = rm.load_voice(vo_report, lang, total, shot_start)
    G, _ = rm.sfx_gain(total, stem_mono, env_db, cue, events, speech, vo, float(20 * np.log10(np.max(np.abs(vo)))))
    sfx = rm.render_sfx(stem_st, band_st, G, speech)
    sf.write(OUT / f"voice_{lang}.wav", np.repeat(vo[:, None], 2, axis=1).astype(np.float32), rm.SR, subtype="PCM_24")
    sf.write(OUT / f"sfx_{lang}.wav", sfx.astype(np.float32), rm.SR, subtype="PCM_24")
    print(lang, "voice peak", round(20 * np.log10(np.abs(vo).max()), 1), "sfx peak", round(20 * np.log10(np.abs(sfx).max() + 1e-12), 1))
print("written", sorted(p.name for p in OUT.iterdir()))
