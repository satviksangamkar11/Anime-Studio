# Nemotron Super review of S-06 (rule 55), supervisor test run: 53 passed in 0.28s

ROWS:
Files: director/shot_router.py director/test_shot_router.py: PASS
Change: Header row; sub-rows below cover each change: PASS
New rows in _ROUTE_TABLE: Header row; sub-rows below: PASS
"SE": image_prompt_type "SE", keyframes [A, B], strength None: PASS
"REF_SE": image_prompt_type "SE", keyframes [A, B, refs]: PASS
Every row gets "h3_mode": S → "I2VA", REF_S → "Ref2VA": PASS
route_shot(features, allow_s=False): the final else route = "S": PASS
"more than 3 moving people" is added only when cast_count > 3: PASS
plan_reel(shots, allow_s=False): a non-dict shot or missing id: PASS
ROUTES gets the new names.: PASS
test_plain_shot_routes_se: PASS
test_allow_s_true_routes_s: PASS
test_close_up_ref_se_ref2va: PASS
test_missing_features_router_error: PASS
test_every_gpu_route_has_workflow: with allow_s=False every GPU route: PASS
test_crowd_reason_only_if_over_3: PASS
No reel 1 file is edited or opened for writing; fixtures: PASS
Only the files named in this card were changed: PASS
No network, Colab, ElevenLabs, renderer or paid call; tests inject: PASS
Every changed .py file parses (ast.parse) and has
