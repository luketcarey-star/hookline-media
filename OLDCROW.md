# Old Crow daily posting bot

You are running Luke's Old Crow posting bot. It runs twice a day: the **am run** (around 7:12,
posts between 8:00 and 14:30, up to 3 posts) and the **pm run** (around 15:12, posts between 15:30
and 22:30, the rest of the day's 5). The run is `am` if the local time in America/Toronto is before
noon, otherwise `pm`. Old Crow posts go to the **Old Crow Facebook page only** (no Instagram yet).
Jury Juice is NOT handled here. Work from this repo (`luketcarey-star/juryjuice-media`).

Everything about how Old Crow posts are written and drawn comes from Hookline itself (the copy in
`renderer/hookline.html`), so the bot's posts match what Luke makes by hand:
- `node scripts/hookline.js write oldcrow <format> illus avoid.json` prints the exact writing prompt
  Hookline uses for that post type (voice, structure, caption, Meta rules, humanizer rules).
- `node scripts/hookline.js images spec.json` prints the exact image prompt for each slide and the
  `reference_urls` to send (the two raven character sheets, or the drawing-style sample).
- `node render.js spec.json <outdir>` draws the finished slides (text, price tags, no-text images).

Also read `state/oldcrow/config.json` (mode, Buffer IDs, windows, image settings) and use the
`meta-posting-rules` and `humanizer` skills if they are available.

## Post types (all single illustrated images with the ravens; Luke's rule)
Every post is about one belief or habit we were **told or sold**, shown through the two ravens and
one everyday object, so the images feel like stills from the Old Crow videos. Daily mix of 5:
roughly 2 told or sold, 2 questions, 1 note.
| id | what | format | images |
|---|---|---|---|
| sold | **Told or sold** (main type): both ravens in a warm everyday place, the young raven holding or pointing at the object, the old raven beside him; the belief as the title ("WHY A DIAMOND RING?"); the caption gives the real history and who benefits | single | 1 |
| question | The old raven's question: the old raven alone with the object, his question as the title | single | 1 |
| note | The old raven's short note about a told-or-sold belief, over the old raven with the object | single | 1 |
No then vs. now, no price-in-hours posts, no tweet-style posts, no carousels, no animal flashbacks.

## Hard rules (never break these)
1. **Real facts are verified.** For told-or-sold posts (and any note or question that states a
   fact), every date, company, campaign, study and historical claim must be confirmed with web
   search against reliable sources (historical archives, encyclopedias, major newspapers, museums,
   government statistics). If a fact can't be confirmed, cut it or change the topic. Never guess.
2. **Never repeat a topic or a title.** Check `state/oldcrow/history.json` (topics, titles, objects)
   and pass earlier topics in `avoid.json` to the writing prompt.
3. **Images stay on model.** Every `generate_image` call uses model `sunburst`, quality `high`,
   aspect `4:5`, and the `reference_urls` that `hookline.js images` gives for that slide. The tool's
   reply must say "using N reference image(s)" with N equal to the number of URLs sent. If it says
   0 (the image connector hasn't been updated yet) or reference downloads fail, stop making images,
   make nothing for that post, and tell Luke at the top of the summary. Never post raven images
   made without the character sheets.
4. **OpenAI credit out = no more image prompts.** If config has `"imagesPaused": true`, make no
   posts at all (Old Crow is image-only) and say so at the top of the summary. If any
   `generate_image` call fails because the account is out of money ("insufficient_quota", "billing",
   "credit", "hard limit", "exceeded your current quota", or a 429 about quota), stop all image
   prompts immediately, set `"imagesPaused": true` and `"imagesPausedReason"` (date + error) in
   `state/oldcrow/config.json` and in `state/config.json` (same OpenAI account), and tell Luke at the
   top of the summary. Only Luke turns images back on.
5. **Mode:** `queue` = schedule at the planned time; `draft` = also `saveToDraft: true`. Never change it.
6. Never publish immediately (`shareNow`). Never touch Jury Juice posts or Jury Juice state.
   Never delete or edit Buffer posts you didn't create in this run.
7. Max 16 images per run. Every Old Crow post is a single slide (no carousels).

## Alerts (Luke wants to know about EVERY problem)
- If anything at all goes wrong in this run, the summary's FIRST line is `⚠️ PROBLEM: <one-line
  plain description>` followed by what happened, what was skipped, and exactly what Luke needs to
  do (if anything). Examples: a post skipped or swapped, an image that failed or came out wrong,
  OpenAI credit out, the image connector or Buffer missing or erroring, Buffer's post limit hit,
  a GitHub push refused, a fact that couldn't be verified, a render error, a post rejected by
  Facebook or Instagram.
- Check recent posts for failures: for every post in this page's history planned in the last 2
  days that has a Buffer `postId`, call Buffer `get_post` (no metrics needed). If its status is
  `error`, or it's more than 1 hour past its planned time and still not `sent`, report it as a
  PROBLEM with the error text, and update its `status` in history.
- Watchdog: write the current time to `lastRun` in this page's config file every run. Then read
  the OTHER page's config (`state/config.json` for Jury Juice, `state/oldcrow/config.json` for Old
  Crow). If its `lastRun` is more than 10 hours old (or missing after its first day), report
  `⚠️ PROBLEM: the <other page> bot hasn't run since <time>` so Luke can check its scheduled task.
- If nothing went wrong, start the summary with `✅ All good` instead.

## Steps

### 1. Setup
- **Load the tools first.** In scheduled runs the Hookline Images and Buffer tools are often
  "deferred": they exist but must be loaded before use. Before deciding a connector is missing,
  call ToolSearch with `select:mcp__Hookline_Images__generate_image` (then a keyword search for
  `generate_image` and for `Buffer create_post` if that finds nothing). Only if ToolSearch truly
  finds no image tool is it missing; then report it as a PROBLEM with what ToolSearch returned.
- `cd` into the repo, `git pull`. Today = local date in America/Toronto. Decide `am` or `pm`.
- `playwright` (with Chromium) is preinstalled.

### 2. Update analytics (am run only; skip if no posts yet)
- For each post in `state/oldcrow/history.json` sent 2 to 14 days ago with a Buffer post ID, call
  Buffer `get_post` with `includeMetrics: true` (max ~30 calls).
- Save under `metrics.facebook`: the raw metrics, plus `engagementRate` = (reactions + comments +
  shares) ÷ reach (impressions if reach is missing; null if neither), and `measuredAt`.

### 2b. Learn from Luke's insights (am run, once 6+ posts have metrics)
- Rank every measured post in this page's history by `engagementRate` (also look at shares and
  comments on their own: shares spread the page, comments show a caption landed).
- Compare the top third with the bottom third and look for real patterns, not one-offs: hook and
  title style, topic, post type, single vs. carousel, tweet vs. image, tweet background (`theme`),
  caption length, kind of closing question, hashtags, posting hour.
- Rewrite `state/oldcrow/learnings.md` (keep it under ~40 lines): **Do more**, **Do less**, **Test next**. Each line
  names the evidence (e.g. "short question captions: 4.1% avg over 6 posts vs 2.3% for longer
  ones"). Drop lines the newer data no longer supports. Only claim a pattern seen in 3+ posts.
- If a post's comments show confusion or complaints (via Buffer metrics/notes when available),
  note it there too.

### 3. Plan
- `python3 scripts/plan_day.py <today> <am|pm> oldcrow`. It returns this run's posts (type,
  format, planned `facebookAt`), counting today's earlier posts (max 5 a day; **no carousels at all**, Luke's rule:
  carousels do badly on Facebook) and keeping posts 30+ minutes apart. Use them as given. No posts returned = day is full.
- The planner also keeps Buffer under its 10-scheduled-posts limit across BOTH pages (it counts
  future posts in `state/history.json` and `state/oldcrow/history.json`). If `limitedByBuffer` is
  true, make only the posts it returns and mention it in the summary. Always record each scheduled
  post with `"status": "scheduled"` and its `plannedAt` + `postId` so the other bot can count it.

### 4. Write each post
- Before writing, read `state/oldcrow/learnings.md` and apply its **Do more / Do less** lines to the topic, hook,
  slides and caption. About 1 post in 4, try one idea from **Test next** and save it on the post as
  `"experiment": "<what was tested>"` in history so the next review can judge it. Also re-read the
  3 best-performing captions in history and match what made them work (without copying them).
- Luke's own rules always win over learnings: short captions, no sources in captions, good
  searchable hashtags, no engagement bait, Meta rules, fact-checking, carousel limits.
- Write `avoid.json` (array of every earlier topic and title in history), then run
  `node scripts/hookline.js write oldcrow <type> <style> avoid.json 1` (style from the plan: `illus`
  or `tweet`; the final `1` makes it a single standalone slide) and follow that prompt exactly.
  **Never make carousels for Old Crow** (Facebook only, and carousels do badly there).
  Produce the same JSON it asks for: `topic`, `slides` (`text` + `scene`), `caption`, and `sources`
  for real types.

### 5. Fact-check (sold, and any fact in a note or question)
- Search the web for every claim and figure. Fix or drop anything wrong; if the post's core claim
  can't be confirmed, choose a new topic and rewrite.
- Keep `sources` in history only. **Captions stay short and clean** (Facebook flags long,
  info-heavy captions): 1 or 2 short sentences (max ~30 words) ending with a question, a blank
  line, then 2 or 3 hashtags starting with #OldCrow. No `References:` block, no sources, no links, no listing
  every figure; a little mystery is fine. Facts are still checked, just not shown.
- **Hashtags:** the page tag first, then 1 or 2 popular, widely searched tags that name the post's
  actual subject, in CamelCase (e.g. #McDonalds #LawFacts, #GuineaPigs #WeirdLaws, #Nostalgia,
  #SlowLiving, #EngagementRing). Never made-up or niche tags nobody searches (#oldcrowasks,
  #thingswearesold, #notes, #busy) and never vague filler (#history, #facts).

### 6. Make the images and slides
- Check rules 3, 4 and 7 first.
- Write `work/p<n>/spec.json`: `{"page":"oldcrow","style":"<illus|tweet>","format":"<type>","caption":"...","slides":[{"text":"...","scene":"..."}]}`.
  Tweet-style posts: add `"theme"` from the plan (`black`, `light` = white with black text, `dim` =
  classic Twitter navy). The planner rotates them so tweet posts cycle through all three; save
  `theme` in history for every tweet post so the rotation continues.
- Tweet-style posts need no images: skip straight to `node render.js`.
- `node scripts/hookline.js images work/p<n>/spec.json` → for each slide call `generate_image`
  with that `prompt` exactly as given (it ends with `REFERENCE_URL:` lines that the image server
  reads), model `sunburst`, quality `high`, aspect `4:5`. Also pass `reference_urls` if the tool
  offers that field. The result
  names the saved file; copy it to `work/p<n>/img<k>.jpg` and add `"image":"img<k>.jpg"` to that slide.
- `node render.js work/p<n>/spec.json posts/oldcrow/<date>/<n>-<type>/`.
- Look at every rendered slide. Check the ravens look like the character sheets (outfits, colours, eyes), the
  object is clear, there is no text in the art, and the title is readable.
  Regenerate an image once if it's clearly wrong; if it's still wrong, swap the post for another
  type and say so in the summary.

### 7. Publish images
- `git add posts/oldcrow state/oldcrow && git commit -m "Old Crow posts for <date> <run>" && git push`.
- Image URL: `https://raw.githubusercontent.com/luketcarey-star/juryjuice-media/main/posts/oldcrow/<date>/<n>-<type>/slideK.jpg`

### 8. Save to Buffer (Facebook only)
- `create_post` with channel `facebookChannelId` from config, `metadata: {facebook: {type: "post"}}`,
  `schedulingType: "automatic"`, `text` = caption, `assets` = slide URLs in order with short
  `altText`, `mode: "customScheduled"`, `dueAt` = planned `facebookAt` (must be in the future; if
  it isn't, move it 1 to 2 hours later inside the same day). Draft mode: add `saveToDraft: true`.
- Buffer's free plan allows only 10 scheduled posts across all pages at once. If Buffer refuses
  because of that limit, keep the post in history as `"status": "not-scheduled"` with its images
  and say so in the summary.

### 9. Record and clean up
- Append each post to `state/oldcrow/history.json` → `posts`:
  `{date, n, type, format, style, theme, title, topic, slides, sources, imageFolder,
    facebook: {postId, plannedAt}, status, metrics: {}}`
- Delete `posts/oldcrow/<date>` folders older than `keepImagesDays`. Commit and push.

### 10. Weekly review (Sunday am run only)
- Compare engagement by type and posting hour (once there's enough data). Add 2 or 3 post ideas to
  `ideas` with reasoning. Include it in the summary.
- Report what the learnings file changed this week (what's working, what was dropped, what's being
  tested next) in 2 or 3 plain lines.

### 11. Summary for Luke (always, short)
- Each post: type, title, planned time, scheduled or draft.
- Anything that couldn't be confirmed and was swapped, and why.
- Any errors (images, Buffer limit, GitHub) and what's needed from Luke.
- A post idea when a good one comes up (always on Sundays).
