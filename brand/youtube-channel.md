# Five Minute AI on YouTube: channel setup (9 Nov 2026)

## Channel

- **Name:** Five Minute AI
- **Handle:** `@fiveminuteai` (if taken: `@fiveminute_ai`, same as Instagram and X)
- **Profile picture:** `brand/youtube-avatar-800.png` (the Instagram picture, 800 x 800)
- **Banner:** `brand/youtube-banner.jpg` (2560 x 1440; everything that matters is in the middle 1546 x 423, which
  every device shows)
- **Links:** fiveminuteai.net (Website), instagram.com/fiveminute_ai (Instagram), linkedin.com/company/fiveminuteai

## Description (paste as is; 468 characters, YouTube allows 1,000)

AI news in 40 seconds, every day.

Spark tells you what happened in AI today, and Doubt, a very sceptical box, asks the questions you'd ask. Every
fact in every Short is checked against its source before it's posted, and the full story, with every source
linked, is on fiveminuteai.net.

New Shorts every day: the AI race between OpenAI, Google, Anthropic, Meta, Microsoft, Nvidia and the challengers,
and what it means for you.

The voices are AI. The checking isn't.

## Settings (YouTube Studio > Settings)

- **Channel > Basic info > Country:** India
- **Channel > Basic info > Keywords:** AI news, artificial intelligence, AI explained, tech news, OpenAI, ChatGPT,
  Google Gemini, Anthropic Claude, Nvidia, AI shorts
- **Channel > Advanced settings > Audience:** "No, set this channel as not made for kids"
- **Upload defaults > Basic info > Visibility:** Public; **Category:** Science & Technology; **Language:** English
- **Upload defaults > Advanced settings > Altered or synthetic content:** our uploads say so themselves
  (the voices are AI); leave the default alone.

## What happens after setup

Every Reel that posts on Instagram is uploaded as a public Short within seconds
(`fma/youtube.py`, from `fma/social_queue.py`), with the Reel's hook as the title (plus #Shorts), the caption
with the real website link as the description, and the AI disclosure set. Its link is saved on the Reel's queue
item (`youtube_url`). 100 uploads a day are allowed; we post 3 to 5.
