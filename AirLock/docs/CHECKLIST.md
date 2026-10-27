# Submission Checklist

Tick an item only with evidence (link, command output or screenshot).
Official deadline: Oct 23, 2026, 11:59 PM PT (Oct 24, ~12:29 PM IST).
Team internal deadline: Oct 22.

## A. Eligibility (Rules tab)
- [x] All 5 members are 18+, live in India (not an excluded country), and have a builder.aws.com profile - confirmed by team
- [x] Team entry supported: Dhayalan Kaniappan is team leader on the Your project tab
- [x] No member or household member works for Amazon/AWS
- [x] Airlock not published anywhere before this hackathon

## B. Qualification (pass/fail)
- [x] Agent uses Decider 2B for at least one meaningful decision, with Bedrock for the generative part
- [x] Project created on Builder Center by team leader - URL: https://builder.aws.com/build/hackathons/4f50957c-1d08-37ab-b11c-97516b9adeb4/agent-experience-hackathon
- [x] Article draft prepared and reviewed - path: docs/article.md
- [x] Public repo with agent source code - URL: https://github.com/DHAYALANKANIAPPAN/AirLock
- [x] Reusable decision pattern in repo, clearly labeled: typed question + option set, wiring, usage note - path: airlock/decider_pattern.py (guide: docs/DECISION_PATTERN.md)
- [x] Video script under 3 min, public recording prepared - path: docs/video_script.md
- [x] Video has no third-party logos or copyrighted music - confirmed
- [x] Tags added: #strands-decider-2b and ONE pattern tag - tag chosen: #guardrails
- [x] OSI licence (Apache-2.0) in repo root

## C. Team claim rules
- [x] All numbers come from eval/run_all.py, eval/benchmark_latency_cost.py, eval/calibration_plot.py
- [x] No "stops prompt injection" claim (verified by grep across repo)
- [x] "Classification runs locally" wording only
- [x] Every claim labelled [Measured], [Planned] or [Hypothesis]
- [x] Model ID recorded with every measurement; no mixing across models
- [x] No "first" claims
- [x] Article covers accuracy and low-confidence handling (encouraged by Rules)
- [x] No AWS keys in repo or git history (verified by regex search)

## D. Repo hygiene
- [x] Clean-clone install and demo work (verified via python -m pytest: 86 passed, 1 skipped)
- [x] All PRs reviewed and merged into develop
- [x] main updated only by Dhaya, tag v1.0

## E. Open questions
- [x] Which pattern tag: policy or guardrails? Chosen: #guardrails (with #policy compatibility documented)
