# ABL build log, reel 1 score (2026-11-09)

Convention: Ableton MCP track_index and clip_index are 1-based. get_track_info reports index 0-based (track 5 shows index 4).

## Baseline (before any change)
- get_session_info: tempo 120.0, 4/4, track_count 4, return_track_count 2, master volume 0.85
- get_arrangement_info: Track 1 "1-MIDI" 0 clips, Track 2 "2-MIDI" 0 clips, Track 3 "3-Audio" 0 clips, Track 4 "4-Audio" 0 clips
- Existing tracks not changed.

## Operations
### OP-01 set_tempo 60
- COMMAND: set_tempo(tempo=60)
- OBSERVED: "Set tempo to 60.0 BPM"; get_session_info tempo 60.0
### OP-02 browser discovery
- get_browser_tree(instruments) and (drums): returned only the root, 0 folders (not useful)
- get_browser_items_at_path(Instruments): Analog, Collision, Drift, Drum Rack, Drum Sampler, DS *, Electric, External Instrument, Impulse, Instrument Rack, Meld, Operator, Sampler, Simpler, Tension, Wavetable. No grand piano, no brass, no choir listed at this level.
- get_browser_items_at_path(Drums): Drum Hits (folder), Drum Rack, and about 200 .adg kits (e.g. 808 Core Kit FileId_5671, 909 Core Kit FileId_5672, Percussion Core Kit FileId_5685, Percussion Spirit Kit FileId_5686)
### OP-03 KP drone (track 5)
- create_midi_track(index -1): "Created new MIDI track: 5-MIDI"
- set_track_name(5, "KP drone"): "Renamed track to: KP drone"
- load_instrument_or_effect(5, query:Synths#Drift): "Loaded instrument ... on track 5"; get_track_info(5) devices: Drift
- create_clip(5, 1, length 73): "Created new clip at track 5, slot 1 with length 73.0 beats"
- add_notes_to_clip(5, 1, 6 notes): "Added 6 notes"
### OP-04 to OP-15 remaining roles (same pattern: create_midi_track, set_track_name, load, create_clip 73, add_notes, duplicate_clip_to_arrangement bar 1 beat 0, set_arrangement_clip_property name)
| Track | Role | Instrument (URI) | Notes added (MCP reply) | Planned |
|---|---|---|---|---|
| 6 | KP pad | Drift (query:Synths#Drift) | 33 | 33 |
| 7 | KP bass | Wavetable (query:Synths#Wavetable) | 146 + 42 = 188 | 188 |
| 8 | KP drums | 909 Core Kit (query:Drums#FileId_5672) | 150 + 122 = 272 | 272 |
| 9 | KP ostinato | Wavetable | 28 | 28 |
| 10 | KP pluck | Analog (query:Synths#Analog) | 3 | 3 |
| 11 | KP lead | Drift | 13 | 13 |
| 12 | KP brass | Analog | 6 | 6 |
| 13 | KP vocal (temp pad) | Drift | 3 | 3 |
| 14 | KP piano | Electric (query:Synths#Electric) | 4 | 4 |
| 15 | KP hits | 808 Core Kit (query:Drums#FileId_5671) | 9 | 9 |
| 16 | KP folk_perc | Percussion Core Kit (query:Drums#FileId_5685) | 13 | 13 |

Track 5 KP drone: Drift, 6 notes (planned 6).
Total notes added: 578 (planned 578).

### Drum pad checks (get_drum_pad_info)
- 909 Core Kit: pads 36, 38, 39, 42, 46 present (GM-like). No remap needed.
- 808 Core Kit: pads 36-51 filled, 74/76/81 not filled. Hits remap at 72.7 s: 74 -> 36, 76 -> 51, 81 -> 47 (recorded as REMAP). The 35.125 s hit at 74 also mapped to 36.
- Percussion Core Kit: pads 41 (Shaker Egg) and 47 (Wood Block Low) present, no remap.

### Mixer (set_track_volume, readback text from each call; get_track_volume(8) = 0.7500)
- KP drone 0.65, KP pad 0.65, KP bass 0.75, KP drums 0.75, KP ostinato 0.70, KP pluck 0.70, KP lead 0.70, KP brass 0.70, KP vocal 0.60, KP piano 0.72, KP hits 0.80, KP folk_perc 0.70

### Arrangement
- set_ableton_view(Arranger): "Switched to Arranger view"
- get_arrangement_info: all 12 new tracks show 1 clip at bars 1-19 (73 beats); clip names match roles.
- get_session_info: tempo 60.0, track_count 16 (4 original + 12 new).

### Known limits
- No note readback tool: note counts are from add_notes_to_clip replies only.
- Instrument presets were not navigated; default device patches were loaded (Drift, Wavetable, Analog, Electric, kits). Sound design still needed.
- No grand piano, brass, or vocal/choir preset found at Instruments root; Electric, Analog, Drift used as stand-ins.
- note_writer returned 7 warnings (not reviewed in this run).
- Not exported (no tool). Owner exports.

## ROUND 2 (coordinator): replace init patches with browser presets; notes untouched
### R2 OP-R2-01 preset loads (load_instrument_or_effect with browser URI; replies "Loaded instrument ...")
- track 5 KP drone -> Sounds/Ambient & Evolving/Dark One.adv (query:Sounds#Ambient%20&%20Evolving:FileId_6862). readback get_track_info: devices = [Dark One (MultiSampler)] only, Drift gone (load replaces the device).
- track 6 KP pad -> Sounds/Ambient & Evolving/Ambiente Pad.adv (FileId_6860)
- track 7 KP bass -> Sounds/Synth Rhythmic/Bass Grinder.adv (FileId_6342)
- track 9 KP ostinato -> Sounds/Synth Rhythmic/Basic Pluck Arp.adg (FileId_4788)
- track 10 KP pluck -> Sounds/Guitar & Plucked/Shimmer Pluck.adg (FileId_5072)
- track 11 KP lead -> Sounds/Winds/Flute Mellow.adv (FileId_6872)
- track 12 KP brass -> Sounds/Brass/Transilvania Brass.adg (FileId_5419)
- track 13 KP vocal -> Sounds/Voices/Choir Reverb.adv (FileId_6879)
- track 14 KP piano -> Sounds/Piano & Keys/Grand Piano.adg (FileId_5119)
- tracks 8 KP drums (909 Core, FileId_5672), 15 KP hits (808 Core, FileId_5671), 16 KP folk_perc (Percussion Core, FileId_5685): already browser kits from round 1, kept.
### R2 OP-R2-02 readback (get_track_info) after presets: every track shows one instrument device (old init device replaced, no delete_device needed)
- 6 KP pad: Ambiente Pad (MultiSampler) | 7 KP bass: Bass Grinder | 9 KP ostinato: Basic Pluck Arp (rack) | 10 KP pluck: Shimmer Pluck (rack) | 11 KP lead: Flute Mellow (Operator) | 12 KP brass: Transilvania Brass (rack) | 13 KP vocal: Choir Reverb (Operator) | 14 KP piano: Grand Piano (rack) | 5 KP drone: Dark One (MultiSampler)

### R2 OP-R2-03 effects
- Reverb (query:AudioFx#Reverb) added after the instrument on tracks 6, 11, 12, 13, 14. Readback: 2 devices on each (instrument + Reverb). Reverb parameters not changed (defaults).
- Glue Compressor (query:AudioFx#Glue%20Compressor) on track 8 KP drums. Readback: devices = 909 Core Kit + Glue Compressor. Parameters default.
- No delay device added. Tempo-sync check: Basic Pluck Arp (track 9) has Arp Rate 1/16 (synced grid, kept as the hypnotic 16ths intent; no free-time option shown). Filter Attack shows 15.0 s; flagged for ear check, not changed.

### R2 OP-R2-04 drum pad re-check (get_drum_pad_info, round 1 readbacks still valid)
- 909 Core Kit (track 8): 36/38/39/42/46 present. No remap.
- 808 Core Kit (track 15): pads 36-51 only; hits remap 74->36, 76->51, 81->47 at 72.7 s (unchanged from round 1).
- Percussion Core Kit (track 16): 41 and 47 present. No remap.

### R2 notes: unchanged. Clips and notes not touched (clip counts unchanged in readbacks: 1 clip each, length 73.0).

### R2 preset picks (browser paths)
- Drone: Sounds/Ambient & Evolving/Dark One.adv
- Pad: Sounds/Ambient & Evolving/Ambiente Pad.adv (not Choiriffic; this is the warm pad)
- Bass: Sounds/Synth Rhythmic/Bass Grinder.adv (not sub-only; a reese-type bass was not located in the browser root listing; Sounds/Bass folder was too large to read in this run)
- Ostinato: Sounds/Synth Rhythmic/Basic Pluck Arp.adg
- Pluck: Sounds/Guitar & Plucked/Shimmer Pluck.adg
- Lead: Sounds/Winds/Flute Mellow.adv
- Brass: Sounds/Brass/Transilvania Brass.adg (dark horn-like, from the Brass folder)
- Vocal (TEMPORARY): Sounds/Voices/Choir Reverb.adv
- Piano: Sounds/Piano & Keys/Grand Piano.adg
- Hits: 808 Core Kit (Drums browser kit, deep 808 boom); no Sounds/Percussive cinematic boom loaded
- Drums: 909 Core Kit (Drums browser kit)
- Folk perc: Percussion Core Kit (Drums browser kit)

## R3 corrected notes (after harmony fixes) - BLOCKED, no mutation made (ABL2, 17:11)
Status: NOT DONE. Nothing was deleted or written on tracks 5-16. Tracks 1-4 untouched.
- Blocker: the Session clip in slot 1 of each KP track cannot be replaced. add_notes_to_clip appends, create_clip refuses an occupied slot ("Clip slot already has a clip", tested on track 5 slot 1), and no tool deletes a session clip or clears its notes.
- Blocker: create_arrangement_midi_clip makes an empty arrangement clip, and no tool adds notes to an arrangement clip, so the arrangement route cannot carry the corrected notes either.
- Read-only state confirmed: tracks 5-16 each have 1 arrangement clip "KP ..." bars 1-19; track 5 session slot 1 has a clip (length 73, playing) with the old notes.
- Corrected note counts from _abl_notes_reel1.json (remap needed for hits: 74->36, 76->51, 81->47; drums 36/38/39/42/46 and folk_perc 41/47 already exist on their kits):
  drone 6 | pad 28 | bass 188 | drums 272 | ostinato 28 | pluck 3 | lead 13 | brass 6 | vocal 3 | piano 4 | hits 9 | folk_perc 13 (total 573)
- Options for the coordinator: (a) delete the 12 session clips by hand in Live, then re-run R3; (b) write the corrected notes to empty session slot 2 on each track and duplicate from slot 2, leaving the stale slot 1 clips to delete by hand. Option (b) changes the session layout, so it needs an OK first.
- Per-track table: notes written 0 of the JSON count on every track 5-16; arrangement clips after = 1 each (unchanged, old notes still in place).

## R3 corrected notes (after harmony fixes) - DONE (ABL2, 17:15)
Coordinator deleted the 12 session slot-1 clips by hand; slot 1 confirmed empty on tracks 5 and 16 before writing.
Per track: old arrangement clip deleted, session clip created (length 73), corrected notes added, duplicated to arrangement bar 1 beat 0, session and arrangement clips named with the track name.
Hits remap applied: 74->36, 76->51, 81->47. Drum pitches 36/38/39/42/46 and folk_perc 41/47 already exist on their kits, no remap.

| Track | Role | Notes in JSON | Notes written (MCP reply) | Arrangement clips after | Readback |
|---|---|---|---|---|---|
| 5 | drone | 6 | 6 | 1 | "KP drone" bars 1-19 |
| 6 | pad | 28 | 28 | 1 | "KP pad" bars 1-19 |
| 7 | bass | 188 | 146+42=188 | 1 | "KP bass" bars 1-19 |
| 8 | drums | 272 | 100+100+72=272 | 1 | "KP drums" bars 1-19 |
| 9 | ostinato | 28 | 28 | 1 | "KP ostinato" bars 1-19 |
| 10 | pluck | 3 | 3 | 1 | "KP pluck" bars 1-19 |
| 11 | lead | 13 | 13 | 1 | "KP lead" bars 1-19 |
| 12 | brass | 6 | 6 | 1 | "KP brass" bars 1-19 |
| 13 | vocal (temp pad) | 3 | 3 | 1 | "KP vocal (temp pad)" bars 1-19 |
| 14 | piano | 4 | 4 | 1 | "KP piano" bars 1-19 |
| 15 | hits | 9 | 9 | 1 | "KP hits" bars 1-19 |
| 16 | folk_perc | 13 | 13 | 1 | "KP folk_perc" bars 1-19 |

Not possible: no note readback tool, so note counts are the add_notes_to_clip replies only. The session clip note contents were not re-read.
Not done by ABL2 (coordinator): Back-to-Arrangement, scale, disarm, track cleanup, save. No clip fired.
