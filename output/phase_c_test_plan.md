# Phase C — Test Plan: AI Video + Licensed B-Roll Workflow
**Generated:** 2026-11-16  
**Status:** AWAITING APPROVAL — do not generate, purchase, or upload anything

---

## Context

The nine-frame static storyboard (Phase B) was rejected. This plan proposes a cinematic production workflow using:
- AI-generated custom football footage (no Content ID exposure, no real match clips)
- Free licensed B-roll from Pixabay for atmospheric context
- CC-BY photos already downloaded in Phase B
- Original animated graphics and motion captions in CapCut / DaVinci Resolve

A single 5-second test clip will be generated (after approval) to validate visual quality before any subscription is purchased.

---

## 1. AI Platform Comparison

### Platform A — Kling AI (klingai.com / app.klingai.com)

| Item | Detail |
|------|--------|
| **Developer** | Kuaishou Technology (China) |
| **Current model** | Kling 4.0 (released October 2026) |
| **App URL** | https://app.klingai.com |
| **API URL** | https://kling.ai/dev |

**Subscription plans (app, USD):**

| Plan | Monthly | Annual/mo | Credits/month | 5-sec clips @ 1080p |
|------|---------|-----------|---------------|---------------------|
| Basic | Free | — | Daily login credits | ~1–3/day (non-commercial) |
| Standard | $8.80 | $6.60 | 660 | ~11 |
| Pro | $32.56 | $24.42 | 3,000 | ~50 |
| Premier | $80.96 | $60.72 | 8,000 | ~133 |

**Credit costs (Kling 3.0 in-app):**
- 720p silent: 6 credits/second → 5-sec clip = 30 credits
- 1080p (standard audio): 12 credits/second → 5-sec clip = 60 credits
- 4K: 30 credits/second → 5-sec clip = 150 credits

**Free tier:**
- Basic plan provides daily login credits (amount varies, typically 50–100/day based on user reports).
- **Hard restriction: free tier outputs carry a Kling watermark and are explicitly NOT licensed for commercial use.** Suitable only for quality testing before subscribing.
- No free trial of paid plans — must subscribe.

**Commercial use:**
- Standard plan and above: commercial use explicitly permitted, watermark-free output.
- Basic/free: commercial use prohibited.

**API access:**
- Full REST API available at https://kling.ai/dev with Python-compatible endpoints.
- Requires prepaid balance — no free API tier.
- API pricing (Kling 4.0): $0.126/second Standard (720p), $0.189/second Pro (1080p).
- 5-second clip via API: $0.63 (Standard) or $0.945 (Pro) — billed per second, no subscription needed.
- Minimum top-up not confirmed from official docs; third-party reseller packages start at ~$9.80.
- **For initial testing: use the browser app (not API). API is better for automated pipeline once approach is validated.**

**CAD cost for a 5-second test clip (Standard plan, 1080p, after subscribing):**
- Standard plan: USD $8.80/month = ~CAD $12.15/month
- 660 credits → 11 × 5-second clips at 1080p
- Cost per clip: ~CAD $1.10
- Full month of 11 clips for CAD $12.15

---

### Platform B — Runway (runway.com)

| Item | Detail |
|------|--------|
| **Developer** | Runway AI, Inc. (USA) |
| **Current models** | Gen-4.5 (native), also resells Kling 4.0 and Seedance 2.0 |
| **App URL** | https://runway.com |
| **API URL** | https://dev.runwayml.com |

**Subscription plans (USD):**

| Plan | Monthly | Annual/mo | Credits/month | 5-sec clips (Gen-4.5) |
|------|---------|-----------|---------------|-----------------------|
| Free | $0 | — | 125 one-time | ~2 total (never replenish) |
| Standard | $15 | $12 | 625 | ~10 |
| Pro | $35 | $28 | 2,250 | ~37 |
| Max | $95 | $76 | 9,500 | ~158 |

**Credit costs:**
- Gen-4.5: 60 credits per 5 seconds
- Kling 4.0 via Runway: 118 credits per 5 seconds at 1080p (more expensive than using Kling directly)
- Seedance 2.0 Pro: 160 credits per 4 seconds

**Free tier:**
- 125 one-time credits on sign-up — never replenish.
- 125 credits = approximately 2 × 5-second clips at Gen-4.5 quality.
- Watermark status on free tier: not confirmed from official pricing page. Likely watermarked (standard industry practice).
- **Usable for one visual quality test without purchase — if watermark-free on free plan.**

**Commercial use:**
- Standard plan and above: commercial use included, no watermark.
- Free plan: restrictions not fully confirmed, assumed non-commercial.

**API access:**
- Full REST API at https://dev.runwayml.com.
- Requires paid plan — no free API tier.
- API credits are separate from subscription.

**CAD cost for a 5-second test clip (Standard plan, Gen-4.5):**
- Standard: USD $12/month (annual) = ~CAD $16.60/month
- 625 credits → ~10 × 5-second clips
- Cost per clip: ~CAD $1.66

---

### Head-to-Head Comparison

| Factor | Kling AI | Runway |
|--------|----------|--------|
| **Free test path** | Yes — daily Basic credits (non-commercial) | Yes — 125 one-time credits (possibly non-commercial) |
| **CAD/month (entry paid)** | ~$12 (Standard) | ~$16 (Standard, annual) |
| **Clips per month (entry paid, 5-sec 1080p)** | ~11 | ~10 |
| **Cost per 5-sec clip (entry paid)** | ~$1.10 CAD | ~$1.66 CAD |
| **Sports/human motion quality** | Kling 4.0 — widely rated best for realistic human athletic movement | Gen-4.5 — strong general quality, slightly less realistic for fast athletic motion |
| **API availability** | Yes (prepaid, Python REST) | Yes (paid plan required) |
| **Browser app** | Yes | Yes |
| **Commercial rights (paid)** | Confirmed Standard+ | Confirmed Standard+ |
| **AI disclosure req. (YouTube)** | Yes — toggle in YouTube Studio | Yes — toggle in YouTube Studio |
| **USA-based entity** | No (Kuaishou, CN) | Yes |
| **Watermark-free** | Standard+ only | Standard+ only |

**Recommendation: Kling AI Standard.**
- Better value at entry tier for this use case (~$12 CAD vs ~$16 CAD).
- Kling 4.0 currently produces more convincing athletic human movement than Gen-4.5 for football-specific shots.
- Free Basic tier allows a no-purchase quality test first.
- Runway remains a strong fallback if Kling's output quality disappoints.

---

## 2. API vs Browser for This Project

**For initial testing and first production: browser app.**
- No code required. Prompt → review → iterate.
- Free test clip possible via Basic daily credits.
- Faster feedback loop for creative direction.

**For scaled production pipeline (future):**
- Kling API integrates with Python. Can be called from `scripts/` directory with API key stored in `.env` (never hardcoded).
- Would allow batch generation of multiple shots from a script.
- Not needed until the visual approach is validated.

---

## 3. Free B-Roll Clips — Verified Assets

All three clips are from Pixabay under the **Pixabay Content License**:  
Commercial use ✓ | Modification ✓ | Attribution not required | No resale of unmodified clips

### CLIP-01 — Stadium Aerial, Empty Field (Daytime)
| Field | Detail |
|-------|--------|
| **Title** | "Soccer Field, Stadium, Aerial View" |
| **Pixabay ID** | 208387 |
| **URL** | https://pixabay.com/videos/soccer-field-stadium-aerial-view-208387/ |
| **Contributor** | ThomaLutfpv |
| **Resolution** | 3840 × 2160 (4K) |
| **Duration** | ~25 seconds |
| **Frame rate** | 59fps |
| **License** | Pixabay Content License — commercial use permitted, no attribution |
| **Visible content** | Empty stadium, aerial/drone, daytime, natural light |
| **Identifiable people** | None — stadium is empty |
| **Logos/branding** | Not confirmed — aerial distance means stadium signage may be visible; must be reviewed before use |
| **Suggested use** | Establishing shot, transition, or background layer |

### CLIP-02 — Evening Football Training, Drone
| Field | Detail |
|-------|--------|
| **Title** | "Football, Training, Evening" |
| **Pixabay ID** | 205193 |
| **URL** | https://pixabay.com/videos/football-training-evening-sport-205193/ |
| **Contributor** | fokus_media |
| **Resolution** | 3840 × 2160 (4K) |
| **Duration** | ~14 seconds |
| **License** | Pixabay Content License — commercial use permitted, no attribution |
| **Visible content** | Football training ground, evening/dusk, drone aerial shot |
| **Identifiable people** | Unlikely at aerial distance — must verify on download |
| **Logos/branding** | Unlikely at drone altitude — verify on download |
| **Suggested use** | Atmospheric B-roll for opening or transition; evokes the pre-match/training atmosphere |

### CLIP-03 — Goalkeeper Action (Match Atmosphere)
| Field | Detail |
|-------|--------|
| **Title** | "Goalkeeper, Soccer, Sports" |
| **Pixabay ID** | 10827 |
| **URL** | https://pixabay.com/videos/goalkeeper-soccer-sports-team-ball-10827/ |
| **Contributor** | Coverr-Free-Footage |
| **Resolution** | 1920 × 1080 (HD) |
| **Duration** | 18 seconds |
| **License** | Pixabay Content License — commercial use permitted, no attribution |
| **Visible content** | Goalkeeper and players in match action |
| **Identifiable people** | ⚠ CAUTION — players are visible in motion. Faces may be identifiable. Under Pixabay license, identifiable people must not be depicted "in a bad light or in an offensive way." A goalkeeper making a save is neutral and flattering — this use is consistent with the license. Confirm on download. |
| **Logos/branding** | Generic kit reported, no club logos noted — verify on download |
| **Suggested use** | Match atmosphere, goalkeeping drama, general football action |

**Download action (after approval):** All three can be downloaded directly from Pixabay at no cost, no account required for HD; 4K may require free account login.

---

## 4. Cinematic 5-Second Test Scene

### Shot: "The Penalty Spot" (Opening/Context shot for Materazzi story)

**Story purpose:** Sets the scene for the story's first factual claim — Materazzi fouled Malouda, France were awarded a penalty. This shot visually anchors the audience before any narration arrives.

**Why this shot first:** It contains no players (no likeness risk), no branded elements (no copyright risk), and is a highly achievable prompt for AI video generators. If the AI can produce a convincing wet-grass penalty spot at night, it can handle the other shots.

---

### Kling / Runway Prompt (exact text, copy-paste ready)

```
Cinematic vertical video, 9:16 aspect ratio. Camera starts at grass level, 
5 centimetres above the turf, slowly pushing forward toward a white penalty spot. 
The ball rests on the penalty spot in sharp foreground. Wet grass reflects the warm 
yellow-white glow of stadium floodlights overhead. The penalty arc is faintly visible 
in the mid-ground. The background shows a massive out-of-focus stadium crowd, 
warmly lit, blurred into a bokeh of amber and white lights. Night. No players visible. 
No team kits. No logos. Shallow depth of field. The movement is slow, deliberate, 
building tension. 24mm equivalent lens. Cinematic colour grade: slightly desaturated 
greens, warm floodlight tones. Slight atmospheric haze. Slow motion. 5 seconds.
```

**Negative prompt (Kling supports this):**
```
people, players, text, watermark, logos, referee, crowd faces close up, 
unrealistic grass, cartoon, animated
```

**Aspect ratio setting:** 9:16 (vertical, for Shorts)  
**Quality:** 1080p Standard (60 credits on Kling, ~$0.80 USD from Standard plan)  
**Duration:** 5 seconds

---

### Why This Prompt Works

| Element | Why it matters |
|---------|----------------|
| Camera at grass level | Creates immediate intimacy and drama — not achievable with static photos |
| Slow push forward | Builds the tension the story requires; no match footage needed |
| Wet grass reflections | Cinematic detail that elevates production quality significantly |
| Stadium crowd bokeh in BG | Anchors the viewer in a live match setting without showing identifiable people |
| No players, no kits, no logos | Eliminates all copyright and likeness risks |
| 9:16 vertical explicit | Ensures correct framing for Shorts without cropping |
| 5 seconds | Matches one story beat; testable within Basic daily credits |

---

## 5. No-Purchase Test Path

Before subscribing to anything, visual quality can be tested using:

**Option 1 — Kling Basic free daily credits (recommended first step):**
1. Create a free account at https://app.klingai.com
2. Log in to receive daily credits (reported 50–100 credits/day for new accounts)
3. Generate at 720p (6 credits/second → 5-sec clip = 30 credits) — fits within one day's free allowance
4. The output will carry a Kling watermark and **cannot be used commercially**
5. This is purely a quality assessment — does Kling produce convincing wet-grass stadium footage?
6. If quality meets the bar: subscribe to Standard (~$8.80 USD/month) and regenerate without watermark

**Option 2 — Runway free 125 credits:**
1. Create a free account at https://runway.com
2. 125 credits = 2 × 5-second clips at Gen-4.5 (60 credits each, 5 credits buffer)
3. Generate the same penalty spot prompt at Gen-4.5 quality
4. Compare visual quality directly against Kling output
5. Free credits do not replenish — use them deliberately

**Both options require no payment to test.**

---

## 6. Expected Costs Summary (CAD)

| Item | Option | CAD Cost |
|------|--------|----------|
| Initial quality test | Kling Basic free credits | $0 |
| Initial quality test (alternative) | Runway free 125 credits | $0 |
| First paid month if quality approved | Kling Standard ($8.80 USD) | ~$12.15 |
| First paid month (alternative) | Runway Standard ($12 USD annual) | ~$16.56 |
| B-roll clips (3 Pixabay clips) | Free download | $0 |
| Music | YouTube Audio Library | $0 |
| Narration (human voice) | macOS + Audacity/DaVinci | $0 |
| Narration (OpenAI TTS, per script) | ~$0.01 USD | ~$0.02 |
| Editing software | CapCut or DaVinci Resolve (free) | $0 |
| **Total for quality test** | | **$0** |
| **Total for first full Short (Kling)** | | **~$12–13 CAD** |

---

## 7. Continue Materazzi or Pivot?

**Recommendation: Continue Materazzi.**

The concept is structurally correct for this workflow:
- The story is told through narration + graphics + mood — not through showing the actual headbutt
- The three verified CC-BY photos (Materazzi, Zidane alone, Zidane + Thuram) provide the specific visual anchors
- AI-generated shots (stadium night, penalty spot, header silhouette, red card moment) fill the cinematic gaps
- The revised script (Phase B) is already written, fact-checked, and ready

Stories with "more accessible footage" do not exist — all real match footage from any significant game is rights-managed. The Materazzi story is well-suited to the narration-driven + atmospheric-B-roll format that successful channels use.

The only change from Phase B: replace static PNG frames with actual video edits in CapCut/DaVinci Resolve, using B-roll + AI clips + photos + animated captions.

---

## 8. Approvals Required Before Proceeding

| Gate | Action |
|------|--------|
| **This plan** | User approval required |
| Free quality test | Create Kling and/or Runway free accounts → generate 1 test clip → review quality |
| Subscription purchase | Only after quality test confirms the approach works |
| B-roll download | After plan approval — download 3 Pixabay clips and inspect for logos/faces |
| Full Short production | After test clip quality approved |
| YouTube upload | Explicit instruction required — not part of this phase |

---

## What Is Explicitly Out of Scope (Unchanged from Phase A/B)

- Real match footage from the 2006 World Cup Final or any broadcast match
- AI-generated likenesses of real, named individuals (Zidane, Materazzi faces)
- Purchasing any subscription or service without explicit approval
- Uploading anything to YouTube
- Editorial-only stock footage used in monetized content
