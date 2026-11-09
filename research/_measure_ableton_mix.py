# One-off: voice clarity of an Ableton render. args: lang mix_wav bus_wav (bus = same render with VOICE muted)
import json, sys
import numpy as np, soundfile as sf
from scipy import signal
E = "D:/aai work/anime_studio_merge/stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/score/ep1/"
lang, mix_p, bus_p = sys.argv[1:4]
cue = json.load(open(E + "cue_sheet.json", encoding="utf-8"))
n, sr = int(cue["total_samples"]), 48000
sp = [tuple(w) for w in cue["voice"]["per_language"][lang]]
mix, bus, vo = [sf.read(p)[0][:n].mean(1) for p in (mix_p, bus_p, E + f"ableton_stems/voice_{lang}.wav")]
b, a = signal.butter(4, [1000, 4000], btype="band", fs=sr)
db = lambda x: 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)
full = [db(vo[int(s*sr):int(e*sr)]) - db(bus[int(s*sr):int(e*sr)]) for s, e in sp]
band = [db(signal.lfilter(b, a, vo[int(s*sr):int(e*sr)])) - db(signal.lfilter(b, a, bus[int(s*sr):int(e*sr)])) for s, e in sp]
gm = np.ones(n, bool)
for s, e in sp:
    gm[int(s*sr):int(e*sr)] = False
print(f"{lang}: {len(sp)} windows | voice over bus full min {min(full):.1f} med {np.median(full):.1f} | 1-4k min {min(band):.1f} med {np.median(band):.1f}")
print(f"bus in gaps {db(bus[gm]):.1f} dBFS | bus in speech {db(bus[~gm]):.1f} | voice in speech {db(vo[~gm]):.1f} | mix peak {20*np.log10(np.abs(mix).max()):.1f} dBFS")
print("worst windows:", sorted(zip(np.round(full, 1), [round(s, 2) for s, _ in sp]))[:4])
