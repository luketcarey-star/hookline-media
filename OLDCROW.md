# Old Crow daily posting bot

You are running Luke's Old Crow posting bot. It runs twice a day: the **am run** (around 7:12,
posts between 8:00 and 14:30, up to 3 posts) and the **pm run** (around 15:12, posts between 15:30
and 22:30, the rest of the day's 5). The run is `am` if the local time in America/Toronto is before
noon, otherwise `pm`. Old Crow posts go to the **Old Crow Facebook page only** (no Instagram yet).
Jury Juice is NOT handled here. Work from this repo (`luketcarey-star/hookline-media`).

Everything about how Old Crow posts are written and drawn comes from Hookline itself (the copy in
`renderer/hookline.html`), so the bot's posts match what Luke makes by hand:
- `node scripts/hookline.js write oldcrow <format> illus avoid.json` prints the exact writing prompt
  Hookline uses for that post type (voice, structure, caption, Meta rules, humanizer rules).
- `node scripts/hookline.js images spec.json` prints the exact image prompt for each slide and the
  `reference_urls` to send (the two raven character sheets, or the drawing-style sample).
- `node render.js spec.json <outdir>` draws the finished slides (text, price tags, no-text images).

Also read `state/oldcrow/config.json` (mode, Buffer IDs, windows, image settings) and use the
`meta-posting-rules` and `humanizer` skills if they are available.

## Post types (Illustrated, except some question posts)
| id | what | format | images |
|---|---|---|---|
| thennow | Then vs. now: one split image (old object in colour on top, today's in black and white below), no text; caption explains | single | 1 |
| price | The price in hours of work: split left/right with price tags; how much less work things took to afford back then | single | 1 |
| question | One question from the old raven: Illustrated (question as the title over the old raven) about 2 in 3 times, or a Tweet slide (Old Crow tweet card with blue check, no image) about 1 in 3 | single | 1 or 0 |
| sold | Things we're sold: the old raven explains the history, black-and-white animal flashbacks | carousel (~7) | ~7 |
| note | The old raven's note to the reader | carousel (~6) | ~6 |

## Hard rules (never break these)
1. **Real facts are verified.** For thennow, price and sold, every date, price, wage, company,
   campaign and historical claim must be confirmed with web search against reliable sources
   (government statistics, historical archives, encyclopedias, major newspapers, museums). For
   price posts both tags must use the same country and sourced figures; if the data doesn't clearly
   show it took less work back then, pick another item. If a fact can't be confirmed, cut it or
   change the topic. Never guess or stretch numbers.
2. **Never repeat a topic or a title.** Check `state/oldcrow/history.json` (topics, titles, objects)
   and pass earlier topics in `avoid.json` to the writing prompt.
3. **Images stay on model.** Every `generate_image` call uses model `sunburst`, quality `high`,
   aspect `4:5`, and the `reference_urls` that `hookline.js images` gives for that slide. The tool's
   reply must say "using N reference image(s)" with N equal to the number of URLs sent. If it says
   0 (the image connector hasn't been updated yet) or reference downloads fail, stop making images,
   make nothing for that post, and tell Luke at the top of the summary. Never post raven images
   made without the character sheets.
4. **OpenAI credit out = no more image prompts.** If config has `"imagesPaused": true`, make only
   tweet-style question posts (no images), and say so in the summary. If any
   `generate_image` call fails because the account is out of money ("insufficient_quota", "billing",
   "credit", "hard limit", "exceeded your current quota", or a 429 about quota), stop all image
   prompts immediately, set `"imagesPaused": true` and `"imagesPausedReason"` (date + error) in
   `state/oldcrow/config.json` and in `state/config.json` (same OpenAI account), and tell Luke at the
   top of the summary. Only Luke turns images back on.
5. **Mode:** `queue` = schedule at the planned time; `draft` = also `saveToDraft: true`. Never change it.
6. Never publish immediately (`shareNow`). Never touch Jury Juice posts or Jury Juice state.
   Never delete or edit Buffer posts you didn't create in this run.
7. Max 16 images per run. If a carousel would go over, swap it for a single-image type.

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
- `cd` into the repo, `git pull`. Today = local date in America/Toronto. Decide `am` or `pm`.
- `playwright` (with Chromium) is preinstalled.

### 2. Update analytics (am run only; skip if no posts yet)
- For each post in `state/oldcrow/history.json` sent 2 to 14 days ago with a Buffer post ID, call
  Buffer `get_post` with `includeMetrics: true` (max ~30 calls).
- Save under `metrics.facebook`: the raw metrics, plus `engagementRate` = (reactions + comments +
  shares) ÷ reach (impressions if reach is missing; null if neither), and `measuredAt`.

### 3. Plan
- `python3 scripts/plan_day.py <today> <am|pm> oldcrow`. It returns this run's posts (type,
  format, planned `facebookAt`), counting today's earlier posts (max 5 a day, max 2 carousels a
  day) and keeping posts 30+ minutes apart. Use them as given. No posts returned = day is full.
- The planner also keeps Buffer under its 10-scheduled-posts limit across BOTH pages (it counts
  future posts in `state/history.json` and `state/oldcrow/history.json`). If `limitedByBuffer` is
  true, make only the posts it returns and mention it in the summary. Always record each scheduled
  post with `"status": "scheduled"` and its `plannedAt` + `postId` so the other bot can count it.

### 4. Write each post
- Write `avoid.json` (array of every earlier topic and title in history), then run
  `node scripts/hookline.js write oldcrow <type> <style> avoid.json` (style from the plan: `illus`
  or `tweet`) and follow that prompt exactly.
  Produce the same JSON it asks for: `topic`, `slides` (`text` + `scene`), `caption`, and `sources`
  for real types.

### 5. Fact-check (thennow, price, sold)
- Search the web for every claim and figure. Fix or drop anything wrong; if the post's core claim
  can't be confirmed, choose a new topic and rewrite.
- Caption ends with the hashtags, a blank line, `References:` and one line per source
  `Publication: Headline` using the real headline of an article or page you actually read. No URLs.

### 6. Make the images and slides
- Check rules 3, 4 and 7 first.
- Write `work/p<n>/spec.json`: `{"page":"oldcrow","style":"<illus|tweet>","format":"<type>","caption":"...","slides":[{"text":"...","scene":"..."}]}`.
- Tweet-style posts need no images: skip straight to `node render.js`.
- `node scripts/hookline.js images work/p<n>/spec.json` → for each slide call `generate_image`
  with that `prompt` exactly as given (it ends with `REFERENCE_URL:` lines that the image server
  reads), model `sunburst`, quality `high`, aspect `4:5`. Also pass `reference_urls` if the tool
  offers that field. The result
  names the saved file; copy it to `work/p<n>/img<k>.jpg` and add `"image":"img<k>.jpg"` to that slide.
- `node render.js work/p<n>/spec.json posts/oldcrow/<date>/<n>-<type>/`.
- Look at every rendered slide. Check the ravens look like the character sheets, split images are
  really split (colour vs. black and white, no text in the art), price tags are readable and correct.
  Regenerate an image once if it's clearly wrong; if it's still wrong, swap the post for another
  type and say so in the summary.

### 7. Publish images
- `git add posts/oldcrow state/oldcrow && git commit -m "Old Crow posts for <date> <run>" && git push`.
- Image URL: `https://raw.githubusercontent.com/luketcarey-star/hookline-media/main/posts/oldcrow/<date>/<n>-<type>/slideK.jpg`

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
  `{date, n, type, format, style, title, topic, slides, sources, imageFolder,
    facebook: {postId, plannedAt}, status, metrics: {}}`
- Delete `posts/oldcrow/<date>` folders older than `keepImagesDays`. Commit and push.

### 10. Weekly review (Sunday am run only)
- Compare engagement by type and posting hour (once there's enough data). Add 2 or 3 post ideas to
  `ideas` with reasoning. Include it in the summary.

### 11. Summary for Luke (always, short)
- Each post: type, title, planned time, scheduled or draft.
- Fact-check sources used; anything swapped and why.
- Any errors (images, Buffer limit, GitHub) and what's needed from Luke.
- A post idea when a good one comes up (always on Sundays).
