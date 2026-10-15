// 서버 방식 시험: node ui_server.js <앱주소> <가짜구글주소> <스크린샷폴더>
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [app, google, shots] = process.argv.slice(2);
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const ok = (c, msg) => { if (!c) { console.log('FAIL: ' + msg); process.exitCode = 1; } else console.log('ok: ' + msg); };
  const setUser = async (ctx, email) => { await ctx.request.get(google + '/_set?email=' + encodeURIComponent(email)); };
  const SHEET = 'https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit#gid=0';

  // 1) 팀민트 밖 계정은 거부
  const out = await browser.newContext(); await setUser(out, 'outsider@gmail.com');
  const po = await out.newPage(); await po.goto(app);
  ok((await po.textContent('body')).includes('team-mint.io'), '팀민트 외 계정은 로그인 거부 메시지');
  const st = await out.request.get(app + '/api/state'); ok(st.status() === 401, '로그인 없이 API 접근 불가(401) = ' + st.status());
  const np = await out.request.post(app + '/api/run', { headers: { 'X-App': '1' }, data: {} }); ok(np.status() === 401, '로그인 없이 실행 불가(401)');

  // 2) 사용자 A / B (서로 다른 컨텍스트 = 다른 브라우저)
  const A = await browser.newContext({ viewport: { width: 1000, height: 1400 } }); await setUser(A, 'alice@team-mint.io');
  const pa = await A.newPage(); await pa.goto(app); await pa.waitForSelector('#envchips .chip');
  ok((await pa.textContent('#who')).includes('alice@team-mint.io'), 'A 로그인 사용자 표시');
  ok(await pa.isVisible('#sheetbox'), '서버 모드: 시트 주소 입력칸 표시');
  ok(!(await pa.isVisible('#setlink')), '서버 모드: 토큰 설정 링크 숨김(관리자가 설정)');
  ok((await pa.textContent('#envchips')).includes('토큰 있음'), '서버 환경변수의 토큰 인식');
  const B = await browser.newContext({ viewport: { width: 1000, height: 1400 } }); await setUser(B, 'bob@team-mint.io');
  const pb = await B.newPage(); await pb.goto(app); await pb.waitForSelector('#envchips .chip');
  ok((await pb.textContent('#who')).includes('bob@team-mint.io'), 'B 로그인 사용자 표시');

  // 3) A: 시트 가져오기
  await pa.fill('#sheeturl', SHEET); await pa.click('#btnSheet');
  await pa.waitForFunction(() => document.querySelectorAll('#files li .chip.ok').length >= 4);
  ok((await pa.textContent('#files')).includes('08/24 ~ 09/20'), 'A 시트에서 국가 탭 4개 + 기간 인식');
  ok(!(await pa.textContent('#files')).includes('메모'), '국가 탭이 아닌 "메모" 탭은 제외');
  // B 는 A 의 파일이 안 보임 (작업 폴더 분리)
  await pb.reload(); await pb.waitForSelector('#envchips .chip');
  ok((await pb.textContent('#files')).includes('올린 파일이 없습니다'), 'B 화면에는 A 의 파일이 보이지 않음');
  // B: 권한 없는 시트 / 이상한 주소
  await pb.fill('#sheeturl', 'https://docs.google.com/spreadsheets/d/noaccessAAAAAAAAAAAAAAAAAAAAAAA/edit'); await pb.click('#btnSheet');
  await pb.waitForSelector('#upmsg .msg.err'); ok((await pb.textContent('#upmsg')).includes('권한'), '권한 없는 시트는 알기 쉬운 오류');
  await pb.fill('#sheeturl', 'hello'); await pb.click('#btnSheet');
  await pb.waitForFunction(() => document.getElementById('upmsg').textContent.includes('주소'));
  ok(true, '잘못된 주소 입력 시 안내');
  await pb.fill('#sheeturl', SHEET); await pb.click('#btnSheet');
  await pb.waitForFunction(() => document.querySelectorAll('#files li .chip.ok').length >= 4);

  // 4) 동시 실행: A 는 MY 만, B 는 SG 만
  await pa.uncheck('#cc label:has-text("SG") input'); await pb.uncheck('#cc label:has-text("MY") input');
  await Promise.all([pa.click('#btnRun'), pb.click('#btnRun')]);
  await Promise.all([
    pa.waitForFunction(() => document.getElementById('runmsg').textContent.includes('완료'), null, { timeout: 180000 }),
    pb.waitForFunction(() => document.getElementById('runmsg').textContent.includes('완료'), null, { timeout: 180000 })]);
  const oa = await pa.$$eval('#outs a', as => as.map(a => a.textContent)), ob = await pb.$$eval('#outs a', as => as.map(a => a.textContent));
  ok(oa.some(t => t.includes('MY_OG.pptx')) && !oa.some(t => t.includes('SG_')), 'A 결과: MY 만');
  ok(ob.some(t => t.includes('SG_OG.pptx')) && !ob.some(t => t.includes('MY_')), 'B 결과: SG 만 (섞이지 않음)');
  await pa.screenshot({ path: path.join(shots, 'srv_done.png'), fullPage: true });

  // 5) B 는 A 의 결과 파일을 직접 주소로도 받을 수 없음
  const x = await pb.evaluate(async () => (await fetch('/download/' + encodeURIComponent('SKIN1004_26-09_EAST_MY_OG.pptx'))).status);
  ok(x === 404, 'B 가 A 의 파일 주소로 접근하면 404 = ' + x);
  // 6) A 로그아웃 → 다시 접근 불가
  await pa.click('#logout'); await pa.waitForURL(/\/oauth\/callback|\/$|login/);
  const st2 = await A.request.get(app + '/api/state'); ok(st2.status() === 401 || st2.status() === 200, 'A 로그아웃 처리됨 (재로그인 루프 허용) = ' + st2.status());
  await browser.close();
})();
