const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const site = path.join(__dirname, '..', 'site');
const read = (file) => fs.existsSync(path.join(site, file)) ? fs.readFileSync(path.join(site, file), 'utf8') : '';

for (const name of ['veriflow', 'ghostqa']) {
  test(`${name}: static case page, contribution and local assets`, () => {
    const html = read(`projects/${name}/index.html`);
    assert.ok(html.includes('外包开发交付案例'), 'case page must exist and identify contracted delivery');
    for (const role of ['思路与方向', 'KIMI K3', 'ChatGPT', 'grok4.6', 'grok4.7', '本地演示环境']) {
      assert.ok(html.includes(role), `missing confirmed role or evidence label: ${role}`);
    }
    const images = [...html.matchAll(/data-full="([^\"]+)"/g)].map(m => m[1]);
    assert.equal(images.length, 3, 'three real case screenshots');
    for (const image of images) assert.ok(fs.existsSync(path.join(site, image.replace(/^\//, ''))), `missing ${image}`);
    assert.match(html, /<dialog[^>]+id="image-viewer"/);
    assert.match(html, /projects\.js/);
    assert.match(html, /rel="canonical"/);
    assert.doesNotMatch(html, /github\.com|(?:\d{1,3}\.){3}\d{1,3}|AIC-\d{4}|<video\b|<iframe\b|\bdownload(?:=|\s|>)/i);
    for (const [, href] of html.matchAll(/href="([^\"]+)"/g)) {
      assert.ok(!/^https?:/.test(href) || href.startsWith('https://ninesense.me/'), `external project link ${href}`);
    }
  });
}

test('homepage selects real projects and preserves competition evidence', () => {
  const html = read('index.html');
  assert.ok(html.includes('href="./projects/veriflow/"'));
  assert.ok(html.includes('href="./projects/ghostqa/"'));
  assert.ok(html.includes('id="competitions"'));
  for (const year of ['award-ccpc-invitational-2026.jpg', 'award-ccpc-northeast-2026.jpg', 'award-liaoning-2025.jpg', 'award-liaoning-2024.jpg']) assert.ok(html.includes(year));
  assert.ok(html.includes('KIMI K3') && html.includes('grok4.7'));
  assert.doesNotMatch(html, /github\.com\/NineSense9\/(?:GhostQA|Veriflow)|(?:\d{1,3}\.){3}\d{1,3}/i);
});

test('detail pages are discoverable and image viewer uses native dialog', () => {
  const sitemap = read('sitemap.xml');
  for (const name of ['veriflow', 'ghostqa']) assert.ok(sitemap.includes(`/projects/${name}/`));
  const js = read('projects/projects.js');
  assert.ok(js.includes('showModal') && js.includes('close'));
  assert.doesNotMatch(js, /innerHTML|insertAdjacentHTML/);
});
