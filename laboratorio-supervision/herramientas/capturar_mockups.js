// Captura las maquetas HTML a PNG (docs/img/hmi_*.png). Requiere Node + Playwright.
//   node herramientas/capturar_mockups.js
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) {
  ({ chromium } = require(path.join(process.env.NODE_PATH || '/opt/node22/lib/node_modules', 'playwright')));
}
(async () => {
  const raiz = path.resolve(__dirname, '..');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  for (const n of ['operador', 'supervisor', 'gerencia']) {
    await page.goto('file://' + path.join(raiz, 'scada', 'mockups', `panel_${n}.html`));
    await page.screenshot({ path: path.join(raiz, 'docs', 'img', `hmi_${n}.png`) });
    console.log('ok', n);
  }
  await browser.close();
})();
