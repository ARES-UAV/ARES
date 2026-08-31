# Repo Cleanup — run in order

Read each block before running it. Commit between blocks so anything can be undone with `git revert`.

Current state: **107 MB working tree, 53 MB of git history**, on a repo with no application code in it yet.

---

## 1. Delete the duplicated experiment tree — recovers 23 MB

`experiments/YOLOv8n/` is a byte-for-byte duplicate of `experiments/Perception/C2A/YOLOv8n/`, left behind when the structure was reorganised in commit `fed3360`. Verified identical, including the `comparisons/` subfolder, which now lives at `experiments/Perception/C2A/comparisons/YOLOv8n/`.

```bash
git rm -r experiments/YOLOv8n
git commit -m "Remove duplicated YOLOv8n tree left over from restructure"
```

---

## 2. Stop tracking redundant weights — recovers 22 MB from the working tree

`YOLOv8s/C2A_finetuning/weights/last.pt` is a *different file* from `best.pt` (checksums differ), but training is finished, so `last.pt` is only useful for resuming a run that will never resume.

```bash
git rm --cached experiments/Perception/C2A/YOLOv8s/C2A_finetuning/weights/last.pt
git commit -m "Untrack last.pt — best.pt is the deployable checkpoint"
```

**Honest caveat:** this shrinks the working tree, not `.git`. Git keeps every version of every file forever, so the 53 MB of history stays 53 MB. Actually reclaiming it means rewriting history with `git-filter-repo`, which invalidates every existing clone.

**Do not rewrite history before 10 September.** 53 MB is survivable; a broken clone two days before the hackathon is not. Revisit it in Phase 2 if you want a clean repo for the paper.

---

## 3. Install the real .gitignore — the urgent one

The current `.gitignore` is one line (`.DS_Store`). The moment you run `npm install` for the frontend, `node_modules/` — roughly 200 MB across tens of thousands of files — becomes stageable. Committing it once would more than triple this repository permanently.

Replace `.gitignore` with the provided one, then:

```bash
git add .gitignore
git commit -m "Add comprehensive gitignore for Python, Node, weights and datasets"
```

Do this **before** creating the frontend.

---

## 4. Fix the folder typo

```bash
git mv experiments/Perception/C2A/YOLOv8n/YOLOv8n_C2A_Finetuned/meterics \
       experiments/Perception/C2A/YOLOv8n/YOLOv8n_C2A_Finetuned/metrics
git commit -m "Fix meterics -> metrics typo"
```

Then update the path references inside `experiments/README.md` if any point at it.

---

## 5. Fill in requirements.txt

It is currently empty, so nobody can reproduce anything. The provided split is deliberate:

- `requirements.txt` — FastAPI + uvicorn + pydantic only. The dashboard backend serves pre-computed detections and must never pull in torch.
- `ai/requirements.txt` — ultralytics, torch, onnx. Install only when training or benchmarking.

```bash
git add requirements.txt ai/requirements.txt
git commit -m "Add split backend / ML dependency files"
```

---

## 6. Fix the README

Three concrete issues:

- **Two headings both titled "System Architecture".** The second one is about adaptive planning — rename it "Adaptive Search Strategy".
- **The Repository Structure section is out of date.** It does not mention `experiments/Perception/`, and lists no `backend/` or `frontend/`.
- **The name conflict.** `README.md` says *Adaptive Rescue and Exploration System*; the pitch deck says *Autonomous Rescue & Environmental Intelligence System*. Pick one. This is the highest-priority documentation fix — a judge reading both will notice.

Worth adding: the built-vs-described scope table from `CLAUDE.md`. Judges reward an honest scope statement, and having it in the README means it is on record before anyone asks.

---

## 7. Add the new files

```
CLAUDE.md                          # repo root — Claude Code reads this automatically
BUILD_ORDER.md                     # repo root
.gitignore                         # replaces the one-line version
requirements.txt                   # replaces the empty one
ai/requirements.txt                # new
experiments/MODEL_SELECTION.md     # new — read this one first
tools/make_fixture.py              # new
```

```bash
git add -A
git commit -m "Add project context, build order, model selection analysis"
```

---

## Not worth doing before 10 September

- Rewriting git history to reclaim the 53 MB
- Squashing or renaming past commits
- Restructuring `ai/`, `planning/`, `simulation/` — they are README-only placeholders and can stay that way
- Setting up CI

None of these affect what a judge sees. Ship the dashboard instead.
