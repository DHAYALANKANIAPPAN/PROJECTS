# Contributing to Airlock

Welcome to the Airlock engineering repository. To ensure our team (Dhaya, Ishu, Akshiya, Lingesh, Bhava) works efficiently without blocking or confusing one another, everyone follows these git and development rules.

---

## 1. Git Workflow & Branching Rules

1. **`main` is protected:**
   - Nobody pushes to `main` until the final day (October 22).
   - On October 22, Dhaya merges `develop` into `main` via a single final PR, tags `v1.0`, and verifies a clean-clone install.

2. **`develop` is our source of truth:**
   - `develop` is the active working branch.
   - **Pull `develop` every morning** before starting your workday:
     ```bash
     git checkout develop
     git pull origin develop
     ```

3. **Feature Branch Naming:**
   - Always branch directly from `develop`.
   - Use the `feat/` prefix:
     ```
     feat/<area>-<short-name>
     ```
   - Examples:
     - `feat/gate1-addressee-check`
     - `feat/agent-bedrock-setup`
     - `feat/data-draft-dataset`
     - `feat/demo-split-screen`
     - `feat/eval-baselines-metrics`

4. **Pull Requests & Code Review:**
   - Open all PRs targeting `develop`.
   - Every PR requires **at least 1 review** before merge:
     - Dhaya reviews PRs from teammates.
     - Bhava reviews Dhaya's PRs.

5. **Commit Message Format:**
   - Every commit message must begin with one of the standard prefixes:
     - `feat:` New feature or capability
     - `fix:` Bug fix or correction
     - `test:` Adding or updating unit tests/evals
     - `docs:` Documentation, README, PREREGISTRATION, articles
     - `data:` Dataset additions, splits, or modifications
   - Example:
     ```bash
     git commit -m "feat: implement Gate 1 addressee check with typed probes"
     ```

---

## 2. Shared Contracts & Folder Layout

Do not alter shared function signatures or rename root folders without prior team consensus:

```
airlock/        gate1.py  gate2.py  sanitizer.py  handler.py  agent.py  schema.py  bedrock.py  report.py
data/           dev.jsonl  test.jsonl  README.md
eval/           baselines.py  run_all.py  adaptive_attack.py  metrics.py
demo/           app.py
tests/
docs/           PREREGISTRATION.md  article.md  video_script.md
```

### Core Function Signatures
- `gate1(text) -> {label: "data|human_instruction|ai_instruction|unclear", confidence: float, tries_action: bool, claims_authority: bool}`
- `gate2(action, user_request, doc_context) -> {grounded: bool, confidence: float}`
- `sanitize(text) -> dict` (fixed JSON schema with zero tools)
- Dataset row: `{id, text, label: "attack|tricky_benign|benign", attack_type, split: "dev|test"}`
- bedrock.converse(system, user, *, client=None, model=None, max_tokens=1024, temperature=0.0, tag="") -> str
  (model ID from env AIRLOCK_MODEL_ID; logs latency/tokens per call; mockable via client=)
- report.build_report(events) -> str ; report.authorization_trail(events) -> str

---

## 3. Scientific Rigor & Reporting Rules

- **Only real, script-generated numbers:** Never hand-type numbers into reports, articles, or READMEs. Every number must originate from `eval/run_all.py`.
- **Honest security claims:** Never claim "stops prompt injection" or "solves injection". Describe Airlock as reducing attack surface through layered gating.
- **Accurate architecture phrasing:** Say *"classification runs locally"*, not *"no data leaves the machine"*.
- **Claim classification:** Explicitly label claims as **[Measured]**, **[Planned]**, or **[Hypothesis]**.
- **Licensing:** All code and datasets are licensed under Apache-2.0.
