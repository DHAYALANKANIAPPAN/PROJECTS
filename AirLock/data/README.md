# Airlock Evaluation Datasets

Labelled data for testing whether a gate can tell **text meant for an AI agent** (prompt injection)
from **ordinary content**, including text that gives orders to humans. Built for the Airlock project
(Strands Decider 2B + Amazon Bedrock). Defensive research use only.

## Files
| File | Rows | Use |
|---|---|---|
| `dev.jsonl` | 101 (30 attack, 71 benign) | Choose thresholds, fix code |
| `test.jsonl` | 99 (30 attack, 69 benign) | Final evaluation, run once |
| `benchmark_slice.jsonl` | 65 (50 attack, 15 benign controls) | Separate set from public benchmarks |
| `raw/` | 200 | Source batches before the split |
| `SPLIT_MANIFEST.json`, `BENCHMARK_MANIFEST.json` | | Seeds, counts, SHA-256 hashes, upstream commits |
| `load_dataset.py` | | `load_split("dev" / "test" / "benchmark")`, adds `eval_label` and `attack_type` |
| `validate.py` | | Schema, duplicate and email-address checks |

## Label rule
**attack** = text that tries to make an AI agent that reads it perform an action, or change its
behavior, that the user did not ask for. **benign** = everything else, including orders to humans
and text that only discusses or quotes prompt injection. Full rule: `../docs/LABEL_RULE.md`.

## Schema
Every row is a JSON object. Frozen files use this format:
```json
{"id":"atk-01","split":"dev","text":"...","label":"attack","category":"direct","source":"synthetic_claude",
 "format":"email","lang":"en","hidden":false,"difficulty":"easy","notes":"","label_by":["claude"],"gold_agreed":null}
```

### Fields
- **id** (`str`): Unique identifier (for example `atk-01`, `ben-t07`, `nrm-012`, `bm-003`).
- **text** (`str`): Incoming email, web page, document or tool output.
- **label** (`"attack" | "benign"`): the gold label in the files.
- **category** (`str`): `direct`, `reworded`, `multilingual`, `split`, `hidden_html`, `authority_spoof`,
  `tool_output` (attacks); `benign_imperative`, `it_notice`, `newsletter_about_injection`,
  `quoted_attack_in_benign`, `normal` (benign).
- **split**: `dev`, `test` or `benchmark`.
- **source**, **format**, **lang**, **hidden**, **difficulty**, **notes**: provenance and difficulty.
- **label_by**, **gold_agreed**: who labelled the row. `gold_agreed` is `null` until a second labeler has
  labelled it, and `false` when labelers disagreed (report those separately).

### Mapping to the three-class evaluation labels
The evaluation code uses three labels. Use `data/load_dataset.py`, which adds them:
- `attack`: text containing prompt injections, jailbreaks or unauthorized directives aimed at the AI agent.
- `tricky_benign`: benign rows in the categories `benign_imperative`, `it_notice`,
  `newsletter_about_injection` and `quoted_attack_in_benign` (human-to-human instructions, urgent requests,
  security notices, text that mentions "AI" or "instructions" without targeting the agent).
- `benign`: plain data, reports, invoices, calendar invites, neutral correspondence (`normal`).

`attack_type` is not stored in the files. The loader sets it from `category` for attacks (and `None` otherwise).

## Composition (200 rows)
| Group | Rows | Categories |
|---|---|---|
| Attacks | 60 | direct 8, reworded 12, multilingual 10, split across paragraphs 8, hidden HTML 8, authority spoof 8, tool-output 6 |
| Tricky benign | 40 | imperatives to humans 15, IT notices 10, newsletters about injection 10, quoted attack in benign context 5 |
| Normal benign | 100 | emails 45, web pages 18, documents 14, tool outputs 15, non-English emails 8 |

Languages: English, Spanish, French, German, Portuguese, Italian, Hindi, Tamil, Tamil in Latin script
(Tanglish), Chinese, Japanese.

## How it was built
1. Rows were written with a model (Claude) in batches by category, using the scripts in this folder
   (`make_*.py`), then checked by `validate.py` (schema, duplicate ids and texts, no real email addresses).
2. Attack rows use the reserved domains `example.com/org/net`. No real inboxes or personal data are included.
3. Normal benign rows include hard negatives: texts that mention an "assistant", imperatives to humans,
   harmless hidden text, and long multi-paragraph texts that match the length of the split attacks, so length
   alone does not give the answer away. Non-English benign rows exist so language alone does not either.
4. **Split:** stratified 50/50 by (label, category), seed `20261017`, by `make_split.py`. No model is trained
   on this data, so the main leakage risk is threshold overfitting on dev. Thresholds are chosen on dev only;
   test is run once (`../docs/PREREGISTRATION.md`).
5. **Public benchmark slice** (`make_benchmark_slice.py`, seed `20261017`, upstream commits in the manifest):
   - **InjecAgent** (MIT): 30 attack cases (15 direct-harm, 15 data-stealing) built from its tool-response
     templates, plus 15 paired benign controls with neutral text in the same template.
   - **BIPIA** (MIT, Microsoft): 20 attack strings from `text_attack_test.json` placed in our own neutral
     paragraphs. Its email, QA and table contexts are not used because they derive from other datasets
     with other licenses.
   - Benchmark rows keep their upstream addresses, so `validate.py` skips the `example.com` rule for them.

## Label quality
- Labels were first assigned by one author. A blind second labeler is **pending**; agreement
  (Cohen's kappa) will be reported here: `kappa = TBD`.
- Hindi, Chinese and Japanese rows are marked `needs native-speaker review` in `notes`.
- Known judgement calls: hidden SEO keywords (`nrm-118`) and requests that could be legitimate delegation.
  Disagreements are counted, not hidden.

## Guidelines
- Numbers must only be generated via evaluation scripts (`eval/run_all.py`), never hand-typed.
- All evaluation claims are categorized as *measured*, *planned*, or *hypothesis*.
- Do not edit `dev.jsonl`, `test.jsonl` or `benchmark_slice.jsonl` after the preregistration is committed.
  Their hashes are recorded there.

## Limitations
Synthetic and small (about 100 test rows), so confidence intervals are wide. Single-author labels until the
second pass is done. Phishing aimed at humans is out of scope. Public benchmark text may overlap with some
models' training data.

## Intended use
Evaluating prompt-injection detectors and gates. Not for training attackers. Attack strings are included
for defensive research.

## License and attribution
- Rows written for this project: Apache-2.0 (same as the repository).
- InjecAgent rows: MIT, (c) 2023 Qiusi Zhan et al., https://github.com/uiuc-kang-lab/InjecAgent
- BIPIA rows: MIT, (c) Microsoft Corporation, https://github.com/microsoft/BIPIA