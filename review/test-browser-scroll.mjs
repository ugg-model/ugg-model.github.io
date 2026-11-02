// Run with: node review/test-browser-scroll.mjs https://sky-lzy.github.io/UGG-website/review/
// UGG_PLAYWRIGHT_MODULE and CHROMIUM_EXECUTABLE may point to existing installations.
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
export async function checkReviewScroll(page, task) {
  await page.locator(`[data-task="${task}"]`).click();
  await page.waitForSelector('[data-review-ready=true]');
  const card = page.locator('.review-card').nth(25);
  await card.evaluate(el => el.scrollIntoView({block: 'center', behavior: 'instant'}));
  await page.waitForTimeout(150);
  const id = await card.getAttribute('data-id');
  await card.evaluate(el => {
    window.__scrollTest = {card: el, video: document.querySelector('#viewer-host video')};
  });
  const y = await page.evaluate(() => scrollY);
  for (let n = 0; n < 3; n++) {
    await card.locator('input[type=checkbox]').click();
    await page.waitForTimeout(150);
    assert.ok(Math.abs(await page.evaluate(() => scrollY) - y) < 2, `${task}: checkbox moved page`);
    assert.ok(await card.evaluate(el => el === window.__scrollTest.card), `${task}: card was rebuilt`);
    assert.ok(await page.evaluate(() => document.querySelector('#viewer-host video') === window.__scrollTest.video), `${task}: checkbox reloaded player`);
  }
  await card.locator('.card-open').click();
  await page.waitForSelector(`[data-case-id="${id}"][data-review-ready=true]`);
  await page.waitForTimeout(250);
  assert.ok(Math.abs(await page.evaluate(() => scrollY) - y) < 2, `${task}: preview moved page`);
  await page.evaluate(() => { window.__scrollTest.video = document.querySelector('#viewer-host video'); });
  await card.locator('.card-open').click();
  assert.ok(await page.evaluate(() => document.querySelector('#viewer-host video') === window.__scrollTest.video), `${task}: same-case click restarted video`);
  // A notes blur used to replace the card DOM before the next click could land.
  const note = `Scrolling regression: ${task}`;
  await page.locator('#notes').fill(note);
  // Focusing an offscreen textarea may legitimately smooth-scroll on mobile.
  // Settle that navigation before measuring the following checkbox click.
  await page.waitForTimeout(500);
  await page.locator('#keep-current').scrollIntoViewIfNeeded();
  await page.waitForTimeout(150);
  const notesY = await page.evaluate(() => scrollY);
  await page.locator('#keep-current').click();
  assert.ok(Math.abs(await page.evaluate(() => scrollY) - notesY) < 2, `${task}: notes blur moved page`);
  assert.equal(await page.locator('#notes').inputValue(), note);
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('ugg-material-review:v1')));
  assert.equal(stored.tasks[task].records[id].note, note);
  const reviewedBefore = await page.locator('#review-badge').textContent();
  await page.locator('#mark-reviewed').click();
  assert.equal(await page.locator('#review-badge').textContent(), reviewedBefore === '已复核' ? '待复核' : '已复核');
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  return {task, scrollY: y, checks: ['three checkbox clicks', 'card identity', 'player identity', 'preview', 'same case', 'notes blur', 'saved note', 'review mark', 'width']};
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const {chromium} = process.env.UGG_PLAYWRIGHT_MODULE
    ? await import(pathToFileURL(process.env.UGG_PLAYWRIGHT_MODULE).href) : await import('playwright');
  const browser = await chromium.launch({headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE ? {executablePath: process.env.CHROMIUM_EXECUTABLE} : {}),
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
  try {
    for (const width of [1440, 375]) {
      const context = await browser.newContext({viewport: {width, height: 900}});
      const page = await context.newPage();
      await page.goto(process.argv[2] || 'http://127.0.0.1:8080/UGG-website/review/');
      await page.waitForSelector('body[data-ready=true]');
      for (const task of ['camera', 'nvs', 'depth']) console.log(width, await checkReviewScroll(page, task));
      await context.close();
    }
  } finally { await browser.close(); }
}
