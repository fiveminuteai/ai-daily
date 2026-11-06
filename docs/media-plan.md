# Sound and motion plan (4 Nov 2026)

**Goal.** Make people stop, stay and click through. Plain text on a coloured card reads like an ad. Two upgrades: a
voice that tells the story, and motion that shows it. Both reach the Reels and the blog.

**Ground rules (unchanged):**
- Every spoken word and every number on screen comes from the fact-checked text. The voice reads only lines that
  passed both checks, and charts use only figures printed in a source.
- Free and owned. The voice is Kokoro-82M (Apache-2.0), run offline on GitHub's machines. The music and all visuals
  are made in code. No stock footage, no AI video models, no logos.
- No cloned or real-person voice. Reels with the synthetic voice carry Meta's AI label, and the caption says
  "Voice: AI".
- One change at a time, so the stats show what worked. Approved or posted Reels never change.

## Phase 1: voiced Reels (sample ready; starts the day after your yes)
- Each scene's line is spoken over the existing music. The music drops to about a quarter while the voice talks.
  - Sample: today's Google Reel, a British male voice and a British female voice. Kokoro has no Indian English voice.
- Captions highlight word by word in time with the voice, for the many viewers who watch with the sound off.
- A pronunciation list for names: Anthropic, Qwen, NotebookLM, Nvidia and others.
- Automatic sound check on every Reel: the run transcribes the finished audio and compares it with the script.
  - Below a 90% word match, that Reel ships without the voice. A bad voice never posts.
  - The first sample scored 1 wrong word in 64 ("Schools" heard as "Goals"). Lines will start a little later after
    each cut.
- Cost: about 1 minute more render time per day. The model (~330 MB) is downloaded once into GitHub's cache.

## Phase 2: animated Reels (the following week)
Motion graphics built from the story's own data:
- **Numbers that move:** bars that grow and counters that tick. "$11.5B → $17B", "48% → 58%".
- **Drawn diagrams:** the post's "how it works" steps draw themselves in time with the voice.
- **The 37 doodles** (fma/sketch.py) draw on stroke by stroke instead of appearing.
- **Kinetic type:** the key word in each line lands on the beat, with a transition between scenes.
- **First frame is the hook:** frame one holds the most striking fact, not a title card.

## Phase 3: the blog page
- **"Listen to today's briefing":** a player at the top of each post, with the whole post read aloud (~6 minutes).
  Its MP3 sits beside the post.
- **Each story shows its Reel inline:** muted autoplay with captions, tap for sound. The video loads only when it
  scrolls into view, with a still image first, so the page stays fast on phones (checked on a 6x CPU-throttled
  phone).
- **Animated charts** in sections that have numbers.

## Phase 4: more places to be found (each needs an account in your name)
- **Podcast:** the daily audio as a podcast feed on Spotify and Apple Podcasts. Free; needs your sign-up.
- **YouTube Shorts:** the same Reels, posted automatically. Needs a YouTube channel and an API key.

## How we'll know it worked
- The Reel stats and the learning loop are already running, so measure one variable at a time:
  - Voiced (from the day after your yes) vs silent (1 Nov onwards): watch time, reach, follows and link clicks.
  - Then animated vs voiced.
- Website visits from Instagram (GoatCounter) and plays of the blog audio.
- Review after 2 weeks of each phase. Keep what moves the numbers; drop what doesn't.

## What I need from you
1. Pick a voice: male, female, or neither. Then say yes to Phase 1 going live.
2. Later, for Phase 4: a Spotify for Creators sign-up and a YouTube channel, both in your name.
