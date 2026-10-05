// Usage: node render.js <spec.json> <outdir>
// spec.json: {"page":"jury","style":"tweet"|"photo","caption":"...","slides":[{"text":"...","image":"path/to/photo.jpg"}]}
// Writes slide1.jpg, slide2.jpg, ... into outdir using Hookline's own drawing code and fonts.
const fs = require("fs"), path = require("path");
const { chromium } = require("playwright");
(async () => {
  const [specPath, outDir] = process.argv.slice(2);
  if (!specPath || !outDir) { console.error("usage: node render.js spec.json outdir"); process.exit(1); }
  const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
  for (const s of spec.slides) {
    if (s.image && !s.image.startsWith("data:")) {
      const p = path.resolve(path.dirname(specPath), s.image);
      const ext = path.extname(p).toLowerCase();
      const mime = ext === ".png" ? "image/png" : ext === ".webp" ? "image/webp" : "image/jpeg";
      s.image = `data:${mime};base64,` + fs.readFileSync(p).toString("base64");
    }
  }
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = []; page.on("pageerror", e => errors.push(e.message));
  await page.goto("file://" + path.join(__dirname, "renderer", "hookline.html"));
  await page.waitForFunction(() => typeof window.hooklineRender === "function");
  const urls = await page.evaluate(spec => window.hooklineRender(spec), spec);
  fs.mkdirSync(outDir, { recursive: true });
  urls.forEach((u, i) => fs.writeFileSync(path.join(outDir, `slide${i + 1}.jpg`), Buffer.from(u.split(",")[1], "base64")));
  await browser.close();
  if (errors.length) console.error("page errors:", errors);
  console.log(`rendered ${urls.length} slide(s) to ${outDir}`);
})();
