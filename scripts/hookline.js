// Ask Hookline (the bot's renderer copy) for the exact prompts it would use.
//
//   node scripts/hookline.js write <page> <format> <style> [avoid.json]
//       Prints the writing prompt (topic auto-chosen; avoid.json = array of earlier topics/titles).
//   node scripts/hookline.js images <spec.json>
//       spec.json = {"page","style","format","slides":[{"text","scene"}]}
//       Prints JSON: one entry per slide with the image prompt and the reference_urls to send.
const fs = require("fs"), path = require("path");
const { chromium } = require("playwright");
const REPO = "luketcarey-star/juryjuice-media";
const RAW = `https://raw.githubusercontent.com/${REPO}/main/refs/`;
const REFS = {
  oldcrow: { sheets: [RAW + "oldcrow-young.jpg", RAW + "oldcrow-old.jpg"], style: [RAW + "oldcrow-flash.jpg"] },
  jury: {}
};
(async () => {
  const [cmd, ...args] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("file://" + path.join(__dirname, "..", "renderer", "hookline.html"));
  await page.waitForFunction(() => typeof window.hooklineWritePrompt === "function");
  if (cmd === "write") {
    const [pg, format, style, avoidFile] = args;
    const avoid = avoidFile ? JSON.parse(fs.readFileSync(avoidFile, "utf8")) : [];
    const out = await page.evaluate(a => window.hooklineWritePrompt(...a), [pg, format, style, 0, avoid]);
    console.log(out);
  } else if (cmd === "images") {
    const spec = JSON.parse(fs.readFileSync(args[0], "utf8"));
    const list = await page.evaluate(s => window.hooklineImagePrompts(s.page, s.style, s.format, s.slides), spec);
    for (const it of list) {
      it.reference_urls = (REFS[spec.page] || {})[it.refs] || [];
      // The image worker reads these lines out of the prompt (works even if the connector strips reference_urls).
      if (it.reference_urls.length) it.prompt += "\n\n" + it.reference_urls.map(u => "REFERENCE_URL: " + u).join("\n");
    }
    console.log(JSON.stringify(list, null, 2));
  } else {
    console.error("usage: write <page> <format> <style> [avoid.json] | images <spec.json>");
  }
  await browser.close();
})();
