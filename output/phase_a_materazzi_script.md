# Phase A — Script: "Everyone Remembers What Zidane Did. Nobody Remembers He Scored."
**Concept:** Concept 3 — Marco Materazzi, 2006 World Cup Final  
**Status:** APPROVED FOR PHASE A  
**Generated:** 2026-11-16  
**Video target:** 25–30 seconds

---

## Fact-Verification Record

All facts below were verified via Wikipedia on 2026-11-16.  
Sources: [2006 FIFA World Cup final](https://en.wikipedia.org/wiki/2006_FIFA_World_Cup_final) · [Marco Materazzi](https://en.wikipedia.org/wiki/Marco_Materazzi) · [Zinedine Zidane](https://en.wikipedia.org/wiki/Zinedine_Zidane)

| Claim | Verified | Source |
|-------|----------|--------|
| France 1–1 Italy at full time and after extra time | ✓ | Wikipedia |
| Zidane scored in the 7th minute (Panenka penalty, hit underside of bar) | ✓ | Wikipedia |
| Materazzi fouled Florent Malouda → conceded penalty | ✓ | Wikipedia |
| Materazzi scored header from Andrea Pirlo corner, 19th minute | ✓ | Wikipedia |
| Materazzi out-jumped Patrick Vieira for the header | ✓ | Wikipedia |
| Zidane headbutt in the 108th minute of extra time | ✓ | Wikipedia |
| Zidane received a straight red card | ✓ | Wikipedia |
| Italy won penalty shootout 5–3 | ✓ | Wikipedia |
| Materazzi scored Italy's second penalty (after Pirlo) | ✓ | Wikipedia |
| Trezeguet missed France's second penalty (hit crossbar) | ✓ | Wikipedia |
| Fabio Grosso scored the winning (fifth) Italian penalty | ✓ | Wikipedia |
| This was Zidane's last professional match | ✓ | Wikipedia |
| Zidane was awarded the FIFA World Cup Golden Ball | ✓ | Wikipedia |
| Materazzi later said "I would prefer your whore of a sister" | ✓ | Wikipedia (Materazzi confirmed in his own book) |

**Facts NOT included in script to avoid complexity:**
- Zidane won the Golden Ball despite the red card (too Zidane-focused, dilutes the Materazzi angle)
- Exact penalty order beyond Materazzi (creates excess detail for 28s)
- What Materazzi said verbatim (not suitable for general audiences without context)

---

## Note on Reference Video Analysis

The discovery dataset contains view counts and titles of high-performing football Shorts.  
**No reference videos were watched.** All format guidance below derives from:
- Title metadata patterns from the 173-video soccer set (player_name_led 56%, narrative hooks, 22–55s duration range observed)
- Published best practices for short-form video structure
- The inherent shape of a "reveal/subvert" narrative (establish assumption → undercut it → layer evidence → payoff)

No claim is made that any specific competitor's editing style, pacing, or caption design caused their view counts.

---

## Final Script

**Total words:** 78  
**Estimated duration:** 27.9s at 2.8 words per second  
**Target duration:** 25–30s ✓

```
[HOOK · 0.0–5.7s · 16 words]
"Everyone knows what Zidane did to Materazzi in 2006."
"Nobody remembers what Materazzi actually did."

[SEQUENCE · 5.7–12.2s · 18 words]
"He fouled Malouda. France scored from the spot."
"Then he headed Italy level. All before the 20th minute."

[ESCALATE · 12.2–16.5s · 12 words]
"108 minutes in — Materazzi said something. Zidane came back. Headbutt. Red card."

[PAYOFF · 16.5–23.3s · 19 words]
"Italy won on penalties. Materazzi scored one of them."
"He shaped that final more than anyone on the pitch."

[KICKER · 23.3–26.5s · 9 words]
"His name is only ever mentioned for the headbutt."

[CTA · 26.5–28.0s · 4 words]
"Follow Beyond The Pitch."
```

---

## Narration Delivery Notes

- **HOOK:** Measured pace. "Everyone knows" — matter-of-fact. Full pause after "2006." Let "Nobody remembers" land quietly. No drama yet.
- **SEQUENCE:** Fast, clipped sentences. Each clause is its own beat. "He fouled Malouda. / France scored. / Then he headed it in. / All in 19 minutes." — rhythm builds.
- **ESCALATE:** Deliberate slow-down before "Materazzi said something." Then speed up: "Zidane came back. Headbutt. Red card." — staccato.
- **PAYOFF:** Return to measured pace. "He shaped that final more than anyone on the pitch." — let it sit.
- **KICKER:** Quiet. Almost understated. The irony does the work.
- **CTA:** Upbeat, brief.

---

## TTS Status

| Option | Commercial use | Cost | Credentials required | Status |
|--------|---------------|------|---------------------|--------|
| macOS Samantha | ✗ NOT for monetized content | — | — | BLOCKED |
| ElevenLabs | ✓ (paid plan) | ~$5/month | ELEVENLABS_API_KEY | BLOCKED — no key in .env |
| Amazon Polly | ✓ | ~$0.004 per script | AWS credentials | BLOCKED — no AWS config |
| OpenAI TTS | ✓ | ~$0.008 per script | OPENAI_API_KEY | BLOCKED — no key in .env |
| Google Cloud TTS | ✓ | ~$0.004 per script | GCP credentials | BLOCKED — no GCP config |

**Recommendation:** OpenAI TTS (tts-1 or tts-1-hd) or Amazon Polly are the lowest-friction options. Both offer male voices suited to sports storytelling. Total cost per script: under $0.02.

**To unblock:** Add one of the following to `.env`:
```
OPENAI_API_KEY=sk-...
```
or
```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=eu-west-1
```

Do not add credentials until ready to produce.
