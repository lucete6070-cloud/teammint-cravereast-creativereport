// 실제 브라우저로 웹 화면을 사람처럼 조작한다. 사용: node ui_e2e.js <앱주소> <CSV폴더> <스크린샷폴더>
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [url, csvDir, shots] = process.argv.slice(2);
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const page = await browser.newPage({ viewport: { width: 1000, height: 1400 } });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  const ok = (c, msg) => { if (!c) { console.log('FAIL: ' + msg); process.exitCode = 1; } else console.log('ok: ' + msg); };

  await page.goto(url);
  await page.waitForSelector('#envchips .chip');
  ok((await page.textContent('#ver')).includes('1.1.0'), '버전 표시');
  ok(await page.isDisabled('#btnRun'), '처음엔 생성 버튼 비활성');
  ok((await page.textContent('#envchips')).includes('토큰 없음'), '토큰 없음 표시');

  // 설정 저장 (토큰은 화면에 다시 안 보여야 함)
  await page.click('text=토큰·계정 설정');
  await page.fill('#tok', 'SECRETTOKEN123');
  await page.fill('#acct-MY', '111'); await page.fill('#acct-SG', '222');
  await page.click('button:has-text("저장")');
  await page.waitForFunction(() => document.getElementById('envchips').textContent.includes('토큰 있음'));
  ok(!(await page.content()).includes('SECRETTOKEN123'), '토큰이 화면에 노출되지 않음');
  ok((await page.inputValue('#tok')) === '', '토큰 입력칸 비움');

  // CSV 올리기 (끌어놓기 대신 파일 선택칸에 설정)
  const files = fs.readdirSync(csvDir).filter(f => f.endsWith('.csv')).map(f => path.join(csvDir, f));
  await page.setInputFiles('#pick', files);
  await page.waitForFunction(() => document.querySelectorAll('#files li').length >= 4);
  ok((await page.textContent('#files')).includes('MY OG'), 'CSV 4개 인식 (국가·유형·기간)');
  ok((await page.textContent('#files')).includes('08/24 ~ 09/20'), '데이터 기간 표시');
  ok(await page.isEnabled('#btnRun'), '준비되면 생성 버튼 활성');

  // 연결 확인
  await page.click('#btnCheck');
  await page.waitForFunction(() => document.getElementById('checkres').textContent.includes('Mock Account'));
  ok(true, '연결 확인(가짜 Meta) 성공 메시지');

  // 언어 전환
  await page.click('#l-vi');
  ok((await page.textContent('#btnRun')).includes('Tạo file'), '베트남어 전환');
  await page.screenshot({ path: path.join(shots, 'ui_vi_ready.png'), fullPage: true });
  await page.click('#l-ko');

  // MY 만 선택해서 실행
  await page.uncheck('#cc label:has-text("SG") input');
  await page.screenshot({ path: path.join(shots, 'ui_ko_ready.png'), fullPage: true });
  await page.click('#btnRun');
  await page.waitForFunction(() => document.getElementById('runmsg').textContent.includes('완료'), null, { timeout: 120000 });
  const outs = await page.$$eval('#outs a', as => as.map(a => a.textContent));
  console.log(outs);
  ok(outs.some(t => t.includes('MY_OG.pptx')) && outs.some(t => t.includes('MY_PR.html')), 'MY 결과 파일 링크');
  ok(!outs.some(t => t.includes('SG_')), '선택하지 않은 SG 는 만들지 않음');
  ok((await page.textContent('#imgtxt')).includes('/'), '이미지 진행 표시');
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#outs a[href*="MY_OG.pptx"]')]);
  const p = path.join(shots, 'dl_' + dl.suggestedFilename()); await dl.saveAs(p);
  ok(fs.statSync(p).size > 100000, '다운로드한 pptx 크기 정상 (' + fs.statSync(p).size + ' bytes)');
  await page.screenshot({ path: path.join(shots, 'ui_ko_done.png'), fullPage: true });

  ok(errors.length === 0, '브라우저 오류 없음 ' + JSON.stringify(errors));
  // 보안: 다른 출처/헤더 없는 쓰기 요청은 거부
  const r1 = await page.evaluate(async () => (await fetch('/api/inputs/clear', { method: 'POST' })).status);
  ok(r1 === 403, '화면이 아닌 곳에서 온 쓰기 요청 거부(403) = ' + r1);
  const r2 = await page.evaluate(async () => (await fetch('/download/..%2F.env')).status);
  ok(r2 === 404, '경로 이동 시도 차단(404) = ' + r2);

  await browser.close();
})();
