# Phase A — Production Requirements: "Everyone Remembers What Zidane Did. Nobody Remembers He Scored."
**Generated:** 2026-11-16

---

## Go / No-Go Status

| Item | Status | Action required |
|------|--------|----------------|
| Script verified | ✓ GO | None |
| All facts fact-checked | ✓ GO | None |
| Photography assets cleared | ✓ GO | Download files from Wikimedia URLs |
| Original graphics feasible | ✓ GO | Build in DaVinci Resolve or CapCut |
| Music option available | ✓ GO | Select specific track (requires listening) |
| SFX available | ✓ GO | Verify individual Freesound files are CC0 |
| Narration voice | ✗ BLOCKER | Add TTS key to .env OR record human voice |
| Fonts | ✓ GO | Download from Google Fonts |
| No match footage in plan | ✓ GO | None |
| No copyrighted audio in plan | ✓ GO | None |

**Production cannot begin until the narration blocker is resolved.**

---

## Hard Blockers (must resolve before any render)

### BLOCKER-1: Commercial TTS Voice
No commercial text-to-speech credentials are configured. macOS Samantha is not licensed for monetized content.

**To unblock (choose one):**
- **Option A — OpenAI TTS:** Add `OPENAI_API_KEY=sk-...` to `.env`. Cost: ~$0.008 for this script. Voice recommendation: `onyx` (deep, authoritative) or `echo` (clear, neutral). Both suit sports storytelling.
- **Option B — Amazon Polly:** Add `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` to `.env`. Cost: ~$0.004. Neural voice recommendation: `Brian` (en-GB) or `Matthew` (en-US).
- **Option C — Human voice recording:** Record directly into DaVinci Resolve or Audacity using any microphone. No cost, no license required. Highest creative control. Recommended if you have access to a suitable voice.

---

## Software Requirements

All software listed below is free:

| Tool | Purpose | Version required | Download |
|------|---------|-----------------|----------|
| DaVinci Resolve (free) | Video editing, text animations, colour grading, Ken Burns, audio mixing | 18+ | blackmagicdesign.com/products/davinciresolve |
| CapCut (free) | Alternative editor — simpler UI, good for text reveals and Ken Burns | Any current | capcut.com |
| Audacity (free) | Audio editing / narration recording if using human voice | Any | audacityteam.org |
| ffmpeg (free) | Optional — batch processing, format conversion | 6+ | ffmpeg.org |

**Note:** CapCut has built-in text-reveal animations and Ken Burns presets. DaVinci Resolve has more precise control over colour grading and the score-flip animation (via Fusion). Either can produce this storyboard.

---

## Asset Checklist (before starting edit)

- [ ] Download `Marco_Materazzi_flickr.jpg` from Wikimedia Commons
- [ ] Download `Zinedine_zidane_wcf_2006.jpg` from Wikimedia Commons
- [ ] Download `Italy_vs_France_-_FIFA_World_Cup_2006_final_-_Lilian_Thuram_and_Zinedine_Zidane.jpg` from Wikimedia Commons
- [ ] Install Oswald Bold and Inter Regular from Google Fonts
- [ ] Select and download music track from YouTube Audio Library (or Kevin MacLeod)
- [ ] Verify and download SFX files from Freesound.org (confirm CC0 license on each)
- [ ] Record or generate narration audio
- [ ] Export narration as WAV or FLAC at 48kHz (YouTube preferred)
- [ ] Confirm `.env` has TTS key OR have human recording ready

---

## Export Specifications

| Setting | Value |
|---------|-------|
| Resolution | 1080 × 1920 (9:16 vertical) |
| Frame rate | 30fps (or 25fps for European distribution) |
| Video codec | H.264 or H.265 |
| Audio codec | AAC, 48kHz, stereo |
| Target file size | Under 50MB (keeps upload time low) |
| Colour space | Rec.709 |
| Duration | 25–30 seconds |

---

## Approvals Required Before Each Phase

| Phase | Gate |
|-------|------|
| Phase A — Creative direction | **User approval of this document** |
| Phase B — Asset gathering | Download CC photos, select music track, resolve TTS blocker |
| Phase C — Edit assembly | User review of rough cut before export |
| Phase D — Export and upload | User explicit approval; do not upload without instruction |

---

## What Is Explicitly Out of Scope

- Match footage or broadcast clips of the 2006 World Cup Final
- Competitor Shorts as visual reference or b-roll
- Any video generation using AI image/video tools without explicit approval
- Uploading anything to YouTube without explicit instruction
- Purchasing any software, service, or stock asset without explicit instruction
