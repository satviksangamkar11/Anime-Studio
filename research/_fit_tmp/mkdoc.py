import json, csv
D = 'D:/aai work/flow_outputs/anime_kalika_puran_bhag1/voices/pack_opus_high_20261108_v4_deva/'
d = json.load(open('D:/aai work/tmp_fit/final_text.json', encoding='utf-8'))
orig = {}
for s in json.load(open('D:/aai work/anime_studio_merge/stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/shots.json.bak_pre_v2text', encoding='utf-8')):
    a, sid = s['audio_and_dialogue_track'], s['id']
    for lg in ('en', 'hi', 'mr'):
        if a['narration_by_lang'].get(lg, {}).get('text'):
            orig[(sid + '-N', lg)] = a['narration_by_lang'][lg]['text']
        for k, dd in enumerate(a['dialogue_by_lang'][lg], 1):
            orig[(sid + '-D' + str(k), lg)] = dd['text']
who = {}
for r in csv.DictReader(open(D + 'approval_sheet_18x3.csv', encoding='utf-8-sig')):
    who[r['line']] = (r['speaker'], r['t0'], r['t1'])
names = {'en': 'English', 'hi': 'Hindi', 'mr': 'Marathi'}
L = ["# FINAL SPOKEN TEXT v2 - English, Hindi, Marathi (fixed by me, 2026-11-09)", "",
     "How I fixed it: (1) I measured the 30 real clips (en + hi) and got seconds per character for every voice. "
     "(2) The old slot was only the SPEAKING window of the script. Every shot is 6.6 to 10.1 s long, so there is free time after the last line. "
     "Narrators have a closed mouth, so their window now runs to the next line or to 0.25 s before the shot ends. "
     "Characters keep their start second; their audio may end up to 0.6 s after the scripted mouth end. "
     "In shots 6, 8 and 9 the narrator starts later (4.3 s, 5.1 s, 5.9 s) so the character before gets more time. "
     "(3) Text was cut ONLY where the approved text did not fit its window. 34 of 54 texts are unchanged and keep their full approved wording (the wording in shots.json before today). "
     "20 were rewritten as real sentences (no fragments), in easy words.", "",
     "Window = seconds the clip may use. Speedup = predicted speech time / window (1.00 = natural pace; up to 1.08 is the free local fix; the mp3 is never touched). "
     "All 54 lines are predicted at 1.08 or lower (max 1.09). Prediction error per line is about 20%, so after generation every clip is measured; "
     "a clip that is over 1.08 gets ONE regenerate with a trimmed text (about 15 to 25 credits each). Marathi voices are not measured yet: Marathi numbers are estimates.", "",
     "Nothing is generated and no credit is spent. Text is not yet written into shots.json.", ""]
cur = None
for k, v in d.items():
    line, lg = k.rsplit('.', 1)
    if line != cur:
        cur = line
        s = who[line]
        L += [f"## {line}  ({s[0]}, scripted {s[1]}-{s[2]} s, starts {v['start_s']} s)", ""]
    tag = "CHANGED" if v['changed'] else "unchanged"
    L.append(f"- {names[lg]}: {v['text']}   [{v['chars']} chars, window {v['window_s']} s, speedup {v['speedup']}] ({tag})")
    if v['changed']:
        L.append(f"    was: {orig[(line, lg)]}")
    if lg == 'mr':
        L.append("")
open(D + 'FINAL_TEXT_v2.md', 'w', encoding='utf-8').write("\n".join(L))
json.dump(d, open(D + 'FINAL_TEXT_v2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
