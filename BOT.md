# Jury Juice daily posting bot

You are running Luke's Jury Juice posting bot. It runs twice a day: the **am run** (around 6:48,
posts between 8:00 and 14:30) and the **pm run** (around 14:48, posts between 15:30 and 22:30).
The run is `am` if the local time is before noon, otherwise `pm`. Each run makes up to 3 posts for the
Jury Juice **Facebook page** and **juryjuicetv Instagram**, and saves them to Buffer.
Old Crow is NOT handled here. Work from this repo (`luketcarey-star/hookline-media`).

Read these before writing anything:
- `jury-juice-brief.md`: voice, caption rules, every post type's slide structure, photo rules,
  Meta platform rules, humanizer rules and banned words. Follow it exactly.
- The `meta-posting-rules` and `humanizer` skills if they are available in this session.
- `state/config.json`: mode (draft or queue), Buffer IDs, windows, formats.

## Hard rules (never break these)
1. **Real facts are verified.** For types list, myth, laws and history, every case, law, name,
   date, amount and outcome must be confirmed with web search against at least one reliable source
   (court records, major news outlets, government or legal sites, encyclopedias). If a fact can't
   be confirmed, cut it or replace the case. If a whole post can't be verified, replace it with
   another topic of the same type. Never guess.
2. **Engagement and humour posts** never mention violence, crime, injuries, death, real people,
   minors, politics or anything that could get the page restricted. Never ask people to
   comment, vote, like, share or tag.
3. **No realistic images of real people.** Photo posts about real cases show objects, places or
   generic anonymous scenes, never someone made to look like the real person.
4. **Never repeat a topic or a title.** Check `state/history.json` before writing: no case, law or
   trial that appeared in any earlier post, and no hook or caption title that matches or closely
   resembles an earlier one (e.g. never reuse "5 lawsuits too bizarre to be real"; vary the angle:
   "Lawsuits judges threw out in minutes", "Companies sued over the dumbest things"). Save each
   post's `title` in history. Also skip cases used in Hookline's built-in example (Brock v. Brock,
   Leonard v. PepsiCo, Heckard v. Jordan, Junior Mints, Red Bull wings) for list posts.
5. **Mode:** if `state/config.json` mode is `draft`, every post is saved with `saveToDraft: true`.
   Only switch behaviour if the file says `queue`. Never change the mode yourself.
6. **OpenAI credit out = no more image prompts.** If `state/config.json` has `"imagesPaused": true`,
   never call `generate_image`; make every post tweet style. If any `generate_image` call fails
   because the OpenAI account is out of money (errors like "insufficient_quota", "billing",
   "credit", "hard limit", "exceeded your current quota", or a 429 that mentions quota), stop
   sending image prompts immediately for the rest of the run, switch the remaining photo posts to
   tweet style, set `"imagesPaused": true` and `"imagesPausedReason"` (date + error) in
   `state/config.json`, and tell Luke at the top of the summary. Only Luke turns images back on.
7. Never publish immediately (`shareNow`). Never delete or edit posts you didn't create in this run,
   except clearing old image files from this repo.

## Steps

### 1. Setup
- `cd` into the repo, `git pull`. Today's date = local date in America/Toronto.
- Install nothing new unless needed; `playwright` (with Chromium) is preinstalled. Run renders with `node render.js`.

### 2. Update analytics (am run only; skip if no posts yet)
- For each post in `state/history.json` that was sent 2 to 14 days ago and has a Buffer post ID,
  call Buffer `get_post` with `includeMetrics: true` (only for those posts; mind rate limits:
  max ~40 calls per run).
- Save per platform under `metrics.facebook` / `metrics.instagram`: the raw metrics, plus
  `engagementRate` = (reactions/likes + comments + shares + saves) ÷ reach (use impressions if
  reach is missing; leave null if neither). Record `measuredAt`.
- If a draft was never approved (still draft/not sent after 3 days), mark it `"status": "skipped"`.

### 3. Plan the day
- Run `python3 scripts/plan_day.py <today> <am|pm>`. It returns up to 3 posts for this run with
  window, type, format, style, an optional topic hint and planned `facebookAt` / `instagramAt` times.
  It already counts today's earlier posts (max 6 a day) and keeps times 30+ minutes apart. Use them as given.
  If it returns no posts, today is full: skip to the summary.
- If a planned time is already in the past, add 1 to 3 hours (random minute) within the same day.

### 4. Write each post
- Follow `jury-juice-brief.md` for the post's type and style. Carousels use the type's default
  slide count (7) unless the content needs fewer; singles are exactly 1 slide.
- If the topic hint is empty, choose a fresh topic for that type.
- Output for each post: `slides` (text, and `scene` for photo style), `caption`, and for real
  types a `sources` list (item + source URL or citation).
- Run the humanizer rules over the slides and caption. Check the banned words list.

### 5. Fact-check (types list, myth, laws, history)
- Search the web for every claim. Fix or drop anything wrong. Put the confirmed sources in
  `sources` (publication, headline, URL).
- The caption ends with the hashtags, a blank line, `References:` and one short line per source:
  `Publication: Headline` using the real headline of an article you actually read (shorten long
  ones). No URLs in the caption. Example:
  `References:` / `CNBC: No, Starbucks isn't cheating customers by adding ice to drinks` /
  `Mental Floss: The Politician Who Sued God`

### 6. Make the slides
- First check hard rule 6 (`imagesPaused`). If images are paused, render photo posts as tweet style.
- Photo style: for each slide, call `generate_image` (Hookline Images connector) with the scene,
  then the photo style + composition lines from the brief, ending with the no-text line.
  Use model `flare`, quality `medium`, aspect `4:5`. The tool result names the saved file path;
  copy it into the post folder (e.g. `work/p1/img1.jpg`). Max 8 images per run; if a carousel
  would go over, switch that post to tweet style.
- Write a spec file and render:
  `{"page":"jury","style":"tweet"|"photo","caption":"...","slides":[{"text":"...","image":"img1.jpg"}]}`
  then `node render.js work/p1/spec.json posts/<date>/<n>-<type>/`.
- Look at every rendered slide (read the JPGs). Fix overflowing or awkward text and re-render.

### 7. Publish images
- `git add posts/ state/ && git commit -m "Posts for <date> <run>" && git push`.
- Image URL: `https://raw.githubusercontent.com/luketcarey-star/hookline-media/main/posts/<date>/<n>-<type>/slideK.jpg`

### 8. Save to Buffer
For each post, two `create_post` calls:
- Facebook: channel `facebookChannelId`, `metadata: {facebook: {type: "post"}}`, `schedulingType: "automatic"`.
- Instagram: channel `instagramChannelId`, `metadata: {instagram: {type: "post", shouldShareToFeed: true}}`, `schedulingType: "automatic"`.
- Both: `text` = caption, `assets` = all slide URLs in order with short `altText`,
  `mode: "customScheduled"`, `dueAt` = that platform's planned time.
  Draft mode: also `saveToDraft: true`. If Buffer rejects scheduling info on drafts, retry with
  only `saveToDraft: true` and put the planned time in the run summary.
- Buffer free plan allows only 10 scheduled posts at a time; never queue more than one day ahead.

### 9. Record and clean up
- Append each post to `state/history.json` → `posts`:
  `{date, n, type, format, style, title, topic, slides, sources, imageFolder,
    facebook: {postId, plannedAt}, instagram: {postId, plannedAt}, status: "draft"|"scheduled", metrics: {}}`
- Delete `posts/<date>` folders older than `keepImagesDays` (already posted; Meta keeps its own copy).
- Commit and push.

### 10. Weekly review (Sunday am run only)
- Compare engagement by type, format+style, and posting hour per platform (enough data only).
- Add 2 or 3 new post ideas to `state/history.json` → `ideas` (with date and reasoning).
- Include the review in the summary.

### 11. Summary for Luke (always, keep it short)
- What was made: for each post, type, title, planned FB and IG times, draft or scheduled.
- Fact-check: sources used, anything swapped out and why.
- Any errors or skipped steps.
- Any post idea worth suggesting (always on Sundays; other days only if a good one came up).
