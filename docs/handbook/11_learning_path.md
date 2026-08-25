# Part 11 — Learning Path

Where you are, what to learn next, in what order, and from where.

---

## 1. Where you actually are

Be accurate about this, because it determines what to do next.

**What you can genuinely do:**

- Train a YOLO model on a custom dataset and read its metrics
- Diagnose a detection/tracking failure by measurement rather than guessing
- Reason about precision/recall trade-offs against a real cost function
- Build a REST API with validated schemas
- Build a React dashboard that keeps its numbers consistent
- Make and defend engineering decisions, with rejected alternatives

That is a genuinely respectable applied-CV skill set. Most undergraduates who
"know YOLO" can run `model.train()` and cannot tell you what mAP50-95 means.

**What you have not done yet:**

- Written a training loop, a loss function, or backpropagation
- Implemented any layer of a neural network
- Trained anything that is not a YOLO fine-tune
- Written tests, or worked in a codebase with more than one contributor
- Read a paper end to end and reimplemented it

**The honest summary:** you are a competent *user* of deep learning tooling and a
capable engineer around it. You are not yet someone who could modify a model
architecture or debug a training run that fails for a reason Ultralytics doesn't
print.

That is a completely normal place to be after one project, and the gap is
closeable in months rather than years.

---

## 2. How to learn this, as opposed to how to feel like you are

Four rules, in rough order of importance.

**1. Build, then read.** You already know this works — you learned more about
tracking from having 333 IDs than you would have from a tracking survey paper.
Have a broken thing in front of you before you go looking for theory.

**2. Reimplement rather than watch.** A tutorial you followed teaches almost
nothing a week later. The same tutorial closed, reimplemented from memory, and
then diffed against the original teaches a lot. The discomfort is the learning.

**3. Measure before you conclude.** This is the single most transferable habit
from ARES. You hypothesised camera motion, measured 1.4 px/frame, and were wrong.
You hypothesised duplicate boxes, measured 1.12 per cluster, and were wrong.
**Both wrong hypotheses were more valuable than a lucky guess**, because the
measurement told you what to rule out.

**4. Explain it to someone.** This handbook exists because you noticed you
couldn't. That instinct is worth keeping — if you cannot explain a thing without
hedging, you do not yet know it.

---

## 3. Tier 1 — finish what you started (next 3 months)

Highest return per hour, because you already have the context loaded.

### Python you are still missing

You have written a lot of Python without meeting some of its machinery. Worth a
weekend each:

- **Type hints and `mypy`** — you use annotations; run a checker against them
- **`pytest`** — your project has no tests. Start with `localize.py`, which is
  pure functions and trivially testable
- **Decorators and context managers** — `@app.get` is a decorator; you should
  know what it does
- **Generators** — `stream=True` returns one. Understand `yield`
- **`dataclasses`** — you use `@dataclass(frozen=True)` in `priority.py`

**Concrete first exercise:** write `backend/test_localize.py`. Assert that the
centre pixel maps to the origin, that a pixel below centre gives a *lower*
latitude, and that `bbox_to_reference_latlon` gives identical pairwise distances
regardless of frame. That last one is a property test of the proof in Part 6.

### PyTorch fundamentals

You have used Ultralytics, which hides PyTorch. Learn what it is hiding.

- **Tensors** — shapes, broadcasting, devices, `.to(device)`
- **`nn.Module`** — how a model is defined
- **Autograd** — `.backward()`, `optimizer.step()`, `optimizer.zero_grad()`
- **`DataLoader`** and `Dataset`

**Resource:** the official [PyTorch 60-Minute Blitz](https://pytorch.org/tutorials/beginner/deep_learning_60min_blitz.html),
then [Learn the Basics](https://pytorch.org/tutorials/beginner/basics/intro.html).
Both are free and short.

**Concrete exercise:** train a CNN on CIFAR-10 with a hand-written training loop.
No Ultralytics, no Lightning. Roughly 100 lines. When it works you will
understand what `model.train()` was doing for you.

### The web gaps

- **`async`/`await`** in both Python and JavaScript. You have used it without
  understanding the event loop
- **The browser devtools Network tab.** This finds CORS and fetch failures in
  seconds and you should be fluent in it
- **Git branching.** You have been committing to `main`. Learn `git branch`,
  `git merge`, and pull requests before you have more collaborators

---

## 4. Tier 2 — proper foundations (6–12 months)

### Deep learning theory

**Pick one and finish it.** Half-finishing three is the standard failure.

| Course | Style | Best for |
|---|---|---|
| [fast.ai — Practical Deep Learning](https://course.fast.ai/) | Top-down: working models first, theory after | You. It matches how you already learn |
| [Stanford CS231n](https://cs231n.github.io/) | Bottom-up, rigorous, CV-specific | If you want to be able to read papers |
| [Andrew Ng — Deep Learning Specialization](https://www.coursera.org/specializations/deep-learning) | Structured, mathematical, gentle | If you want a certificate and steady pacing |

**My recommendation: fast.ai first, then CS231n.** fast.ai will feel natural
because it starts where you already are. CS231n then fills in the mathematics —
and its assignments make you implement backprop by hand, which is the thing that
converts "I use neural networks" into "I understand them."

CS231n's notes are free and public even when the course isn't running.

### The mathematics you actually need

Do not do a full maths degree. You need three things:

**Linear algebra** — matrix multiplication, dot products, eigenvectors.
→ [3Blue1Brown, *Essence of Linear Algebra*](https://www.3blue1brown.com/topics/linear-algebra).
Fifteen short videos, and the best mathematics exposition on the internet.

**Calculus** — derivatives, chain rule, partial derivatives. That is what
backpropagation *is*.
→ [3Blue1Brown, *Essence of Calculus*](https://www.3blue1brown.com/topics/calculus).

**Probability and statistics** — distributions, expectation, Bayes. Underlies
loss functions and evaluation.
→ StatQuest with Josh Starmer, on YouTube. Unreasonably clear.

### Computer vision specifically

- **Convolutions** — what a kernel does, stride, padding, receptive field
- **Architectures** — ResNet (residual connections), U-Net (segmentation),
  Vision Transformers, and why YOLOv12 borrowed attention
- **Detection heads** — anchor-based vs anchor-free, FPN, NMS
- **Augmentation** — mosaic, mixup, and why they help small-object detection

**Resources:**
- [Ultralytics documentation](https://docs.ultralytics.com/) — read it properly,
  not just the page you needed. It is unusually good
- [Roboflow's blog](https://blog.roboflow.com/) — practical, current, well-written
- [PyImageSearch](https://pyimagesearch.com/) — long-form tutorials, strong on
  fundamentals

**Papers to read in order.** Read the abstract, the figures, and the results
table first; the method section last.

1. **YOLOv1** (Redmon et al., 2016) — the original one-stage idea, still readable
2. **Faster R-CNN** — the two-stage approach, so you know what YOLO replaced
3. **ByteTrack** — the tracker you are actually using
4. **YOLOv12** — [arXiv:2502.12524](https://arxiv.org/abs/2502.12524). Your model
5. **SAHI** — tiled inference for small objects, which is your best available
   accuracy win

### Software engineering

This is where most self-taught ML people are weakest, and it is where employers
notice.

- **Testing** — `pytest`, fixtures, parametrised tests, property-based testing
  with Hypothesis
- **Type checking** — `mypy` in CI
- **CI/CD** — GitHub Actions running your tests on every push
- **Docker** — reproducible environments. Would have prevented your Colab
  disaster
- **Code review** — the fastest way to improve, and you need a collaborator for it

---

## 5. Tier 3 — where this could go

### If you continue with ARES

**Thermal fusion.** RGB and thermal are complementary — thermal sees through
smoke and darkness, RGB has the resolution. Fusion can happen early (stack the
channels), late (fuse detections), or mid-network. Public datasets: KAIST
Multispectral Pedestrian, FLIR ADAS, LLVIP.

**Hazard classification.** AIDER is the right dataset — UAV-native, unlike xBD
which is satellite. Same training pipeline as your survivor model.

**SLAM and GPS-denied navigation.** The hardest item on your list, deliberately
deferred. If you want to build it: ORB-SLAM3 is the canonical open implementation,
and visual-inertial odometry is the sub-problem to understand first.

**Path planning.** Your "safe route" extension. A*, D* Lite, RRT*. This is
classical robotics, well-taught, and satisfying to implement.

### The research paper

Your project context names an eventual paper on **adaptive, risk-aware search
prioritization.** That is a real contribution area and your priority scoring is
the seed of it.

To make it a paper you need three things you do not have:

1. **A baseline to beat.** Right now there is nothing to compare your ranking
   against. Random order? Confidence order? Nearest-first?
2. **A metric.** "Time to locate all survivors" or "expected survivors found in
   the first N minutes", simulated over many scenarios.
3. **Ablations.** Show that each term contributes. Your term-drop machinery
   already gives you the mechanism to run these.

**A faculty mentor makes this dramatically easier**, and SIH requires one anyway.
Ask early.

### eYRC

e-Yantra themes are robotics-focused and reward exactly the skills this project
built: embedded work, computer vision, systems integration. The transferable
pieces are on-device inference, coordinate transforms, and having shipped
something end to end.

---

## 6. A concrete 12-week plan, starting after 20 September

| Weeks | Focus | Deliverable |
|---|---|---|
| 1–2 | PyTorch fundamentals | CIFAR-10 CNN with a hand-written training loop |
| 3–4 | Testing | `pytest` suite for `backend/`, GitHub Actions running it |
| 5–8 | fast.ai Part 1 | Finish it. All notebooks run, one project of your own |
| 9–10 | Papers | Read the five above. Write a one-page summary of each |
| 11–12 | Reimplement | Build a minimal detector from scratch — grid, boxes, one loss |

**Then reassess.** Twelve weeks of that puts you meaningfully ahead of where
"knows YOLO" gets you.

### Two rules for the plan

**Ship something every two weeks.** A repo, a notebook, a blog post. Unshipped
learning evaporates.

**Write down what you tried that did not work.** Your ARES decision log is the
most valuable document in that repo. Keep the habit — it is also the raw material
for a paper's related-work section and for every interview you will ever do.

---

## 7. Channels and sites worth following

**YouTube**
- **3Blue1Brown** — mathematical intuition. Start with neural networks
- **StatQuest** — statistics, unreasonably clear
- **Andrej Karpathy** — "Neural Networks: Zero to Hero" builds GPT from scratch.
  Language rather than vision, but the best deep-learning teaching that exists
- **Two Minute Papers** — keeps you aware of what's happening
- **Nicholas Renotte** — practical CV projects, similar to your level

**Reading**
- [Ultralytics docs](https://docs.ultralytics.com/) and blog
- [Roboflow blog](https://blog.roboflow.com/)
- [PyImageSearch](https://pyimagesearch.com/)
- [The AI Summer](https://theaisummer.com/) — good conceptual explainers
- [Papers with Code](https://paperswithcode.com/) — papers with implementations
- **Hugging Face** — increasingly the centre of gravity for models and datasets

**Practice**
- **Kaggle** — competitions and public notebooks. Read the winners' write-ups
- **Roboflow Universe** — public CV datasets, well-annotated

---

## 8. What to do in the next two weeks

Not learning. Shipping.

- [ ] Run the Pi benchmark when the SD card arrives — **at `imgsz=960`**
- [ ] Run `compare_trackers.py` to a conclusion
- [ ] Fix the two labelling issues: `cluster_formed`, and "22 **others** within
      15 m"
- [ ] Reconcile the 3 m/s vs 5 m/s inconsistency
- [ ] Verify the static-mode fallback with the backend actually stopped
- [ ] Verify the tile cache with wifi actually off
- [ ] **Count people by hand in three frames** and compare to 23. This is the
      highest-value hour left in the project
- [ ] Read Part 10 twice

**Learning resumes on 21 September.** Until then the only thing that matters is
that the demo works and you can explain it.

---

## What to take from this part

- You are a capable *user* of deep learning tooling. The gap to *practitioner* is
  PyTorch fundamentals and one finished course.
- **Build, then read.** Reimplement rather than watch. Measure before concluding.
- fast.ai first, CS231n second, 3Blue1Brown alongside both.
- Testing and Docker are where self-taught ML people are weakest and where you
  would gain most.
- **Keep the decision log habit.** It is the single most valuable artefact you
  produced.

---

**Sources:**
[CS231n — Deep Learning for Computer Vision](https://cs231n.github.io/) ·
[Best Computer Vision Courses — Roboflow](https://blog.roboflow.com/best-computer-vision-courses/) ·
[Ultralytics Docs](https://docs.ultralytics.com/) ·
[Top Resources for Computer Vision and Deep Learning — AI Summer](https://theaisummer.com/computer-vision-resources/) ·
[Best Object Detection Models — Ultralytics](https://www.ultralytics.com/blog/best-object-detection-models)
