const { chromium } = require('playwright');
const fs = require('fs');
const DIR = 'C:/Users/AiMiniX/AppData/Local/Temp/claude/C--Users-AiMiniX/962c19a7-f6e5-4098-931c-e1e4d48bf058/scratchpad';
(async () => {
  const html = fs.readFileSync('C:/Users/AiMiniX/open-webui/templates/artifacts/onem_multiseries_chart.html','utf8');
  const b = await chromium.launch({headless:true});
  const p = await b.newPage({viewport:{width:820,height:520}});
  await p.setContent(html, {waitUntil:'networkidle'});
  await p.waitForTimeout(600);
  const bars = await p.locator('rect.bar').count();
  const legends = await p.locator('.legend span').count();
  console.log('bars_rendered:', bars, '| legend_series:', legends);
  await p.screenshot({path:`${DIR}/chart_render_full.png`});
  // hover a bar (tooltip) then toggle 3rd series off
  await p.locator('rect.bar').nth(7).hover();
  await p.waitForTimeout(400);
  await p.screenshot({path:`${DIR}/chart_render_hover.png`});
  await p.locator('.legend span').nth(2).click();
  await p.waitForTimeout(500);
  const barsAfter = await p.locator('rect.bar').count();
  console.log('bars_after_toggle_3rd_off:', barsAfter, '(ควรน้อยลง 6 แท่ง)');
  await p.screenshot({path:`${DIR}/chart_render_toggled.png`});
  await b.close();
})();
