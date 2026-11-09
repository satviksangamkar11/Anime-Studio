import json, shutil, sys
P = 'D:/aai work/anime_studio_merge/stories/kalika_puran_bhag1/pack_opus_high_20261108_v4_deva/shots.json'
raw = open(P, encoding='utf-8').read()
shots = json.loads(raw)
rt = json.dumps(shots, ensure_ascii=False, indent=1)
print('roundtrip identical:', rt == raw.rstrip('\n'), len(rt), len(raw))
final = json.load(open('D:/aai work/tmp_fit/final_text.json', encoding='utf-8'))
if '--apply' not in sys.argv:
    sys.exit(0)
shutil.copy(P, P + '.bak_pre_v2text')
changed = []
for s in shots:
    a, sid = s['audio_and_dialogue_track'], s['id']
    for lg in ('en', 'hi', 'mr'):
        n = a['narration_by_lang'].get(lg, {})
        if n.get('text'):
            new = final[f'{sid}-N.{lg}']['text']
            if n['text'] != new:
                changed.append(f'{sid}-N.{lg}')
                n['text'] = new
        for k, d in enumerate(a['dialogue_by_lang'][lg], 1):
            new = final[f'{sid}-D{k}.{lg}']['text']
            if d['text'] != new:
                changed.append(f'{sid}-D{k}.{lg}')
                d['text'] = new
    if a['narration'].get('text'):
        a['narration']['text'] = final[f'{sid}-N.en']['text']
    for k, d in enumerate(a['dialogue'], 1):
        d['text'] = final[f'{sid}-D{k}.en']['text']
open(P, 'w', encoding='utf-8').write(json.dumps(shots, ensure_ascii=False, indent=1) + ('\n' if raw.endswith('\n') else ''))
json.load(open(P, encoding='utf-8'))
open('D:/aai work/tmp_fit/applied.txt', 'w').write(str(len(changed)) + ' changed: ' + ', '.join(changed))
