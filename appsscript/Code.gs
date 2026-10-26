/**
 * Creative Report 생성기 — Apps Script 서버 코드 (설치·서버·결제 없이 주소만 열면 되는 방식).
 * 배포: 웹 앱, "실행: 나", "액세스: team-mint.io 사용자". 순서는 docs/AppsScript_배포.md.
 *
 * 스크립트 속성(프로젝트 설정 > 스크립트 속성)에만 넣는 값 — 코드·채팅·문서에 쓰지 않는다:
 *   META_ACCESS_TOKEN            Meta 장기 토큰 (약 60일)
 *   META_TOKEN_ISSUED            발급일 YYYY-MM-DD (50일 지나면 화면에 갱신 안내)
 *   META_AD_ACCOUNT_ID_MY / _SG / _ID / _PH   국가별 광고계정 ID (숫자 또는 act_숫자). 한 국가에 계정이 여럿이면 쉼표로: ID 는 "Shopee계정,Tokopedia계정"
 *   TEMPLATE_FILE_ID             드라이브에 올린 양식 pptx 의 파일 ID (비우면 화면에서 양식 파일을 직접 고름)
 */
var VERSION = '2.0.0';
var GRAPH = 'https://graph.facebook.com/v21.0/';
var TAB = /^([A-Za-z]{2})_(OG&TEST|PR&BR)$/;
var STATUSES = ['ACTIVE', 'PAUSED', 'ARCHIVED', 'CAMPAIGN_PAUSED', 'ADSET_PAUSED', 'PENDING_REVIEW', 'DISAPPROVED', 'WITH_ISSUES', 'IN_PROCESS'];

function doGet() {
  var t = HtmlService.createTemplateFromFile('Index');
  return t.evaluate().setTitle('Creative Report 생성기').addMetaTag('viewport', 'width=device-width, initial-scale=1');
}
function include(name) { return HtmlService.createHtmlOutputFromFile(name).getContent(); }

/** 관리자가 편집기에서 한 번 실행해 권한(드라이브·시트·외부 연결)을 승인하는 용도. 새 권한이 추가된 뒤 승인하지 않으면
 *  화면에 "현재 사용할 수 있는 서버가 없습니다" 같은 오류가 난다. 실행 후 "배포 관리 > 새 버전" 을 한 번 더 한다. */
function authorize() {
  var id = props().getProperty('TEMPLATE_FILE_ID');
  var name = id ? DriveApp.getFileById(id).getName() : '(TEMPLATE_FILE_ID 없음)';
  UrlFetchApp.fetch('https://graph.facebook.com/v21.0/', { muteHttpExceptions: true });
  SpreadsheetApp.getActiveSpreadsheet();   // 시트 권한 (null 이어도 됨)
  Logger.log('권한 승인 완료. 양식 파일: ' + name);
  return '권한 승인 완료. 양식 파일: ' + name;
}
function props() { return PropertiesService.getScriptProperties(); }

/** 화면 첫 로딩: 사용자·버전·설정 상태 (토큰 값은 절대 돌려주지 않음) */
function getState() {
  var p = props(), accounts = {};
  ['MY', 'SG', 'ID', 'PH'].forEach(function (c) { accounts[c] = !!p.getProperty('META_AD_ACCOUNT_ID_' + c); });
  var issued = p.getProperty('META_TOKEN_ISSUED') || '', days = null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(issued)) days = Math.floor((Date.now() - new Date(issued + 'T00:00:00Z').getTime()) / 86400000);
  return { user: Session.getActiveUser().getEmail(), version: VERSION, hasToken: !!p.getProperty('META_ACCESS_TOKEN'),
           accounts: accounts, issued: issued, tokenDays: days, hasTemplate: !!p.getProperty('TEMPLATE_FILE_ID') };
}

/** 연결 확인: 국가별 광고계정 이름 조회 (토큰·권한이 살아 있는지) */
function checkConnection(countries) {
  var p = props(), token = p.getProperty('META_ACCESS_TOKEN'), out = [];
  if (!token) return [{ level: '오류', ko: '토큰이 없습니다. 관리자가 스크립트 속성 META_ACCESS_TOKEN 을 넣어야 합니다.', vi: 'Chưa có token. Quản trị viên cần đặt META_ACCESS_TOKEN.' }];
  (countries || []).forEach(function (cc) {
    var accts = accounts_(p, cc);
    if (!accts.length) { out.push({ level: '주의', ko: cc + ' 광고계정 ID 가 없습니다 (META_AD_ACCOUNT_ID_' + cc + ').', vi: 'Thiếu ID tài khoản quảng cáo ' + cc + '.' }); return; }
    accts.forEach(function (acct) {
      try {
        var r = graphGet_(acct, { fields: 'name' }, token);
        out.push({ level: 'OK', ko: cc + ' 광고계정 연결 확인: ' + r.name, vi: 'Kết nối tài khoản ' + cc + ': ' + r.name });
      } catch (e) { out.push({ level: '오류', ko: cc + ' 광고계정(' + acct + ') 연결 실패: ' + e.message, vi: 'Lỗi kết nối tài khoản ' + cc + ': ' + e.message }); }
    });
  });
  var s = getState();
  if (s.tokenDays !== null && s.tokenDays >= 50) out.push({ level: '주의', ko: '토큰 발급 후 ' + s.tokenDays + '일 지났습니다 (약 60일 만료). 관리자에게 갱신을 요청하세요.', vi: 'Token đã ' + s.tokenDays + ' ngày (hết hạn ~60 ngày). Hãy nhờ quản trị viên gia hạn.' });
  return out;
}

/** 시트 주소 → 국가 탭 값(표시된 값 그대로). 빈 꼬리 행은 잘라 전송량을 줄인다. */
function readTabs(text) {
  var m = /\/spreadsheets\/d\/([A-Za-z0-9_-]+)/.exec(text || '');
  var id = m ? m[1] : (text || '').trim();
  if (!id) throw new Error('구글 시트 주소(https://docs.google.com/spreadsheets/d/...)를 붙여넣어 주세요 / Hãy dán địa chỉ Google Sheet');
  var ss;
  try { ss = SpreadsheetApp.openById(id); }
  catch (e) { throw new Error('이 시트를 볼 수 있는 권한이 없거나 주소가 틀렸습니다. 본인 계정으로 시트가 열리는지 확인하세요 / Bạn không có quyền xem sheet này hoặc địa chỉ sai'); }
  var title = ss.getName(), pm = /\((\d{2})\/(\d{2})-(\d{2})\/(\d{2})\)/.exec(title);
  if (!pm) throw new Error("시트 제목에 데이터 기간 '(08/24-09/20)' 이 없습니다: " + title + ' / Tiêu đề sheet thiếu khoảng thời gian dữ liệu');
  var tabs = [];
  ss.getSheets().forEach(function (sh) {
    var tm = TAB.exec(sh.getName()); if (!tm) return;
    var vals = sh.getDataRange().getDisplayValues();
    var last = vals.length; while (last > 0 && vals[last - 1].every(function (v) { return v === ''; })) last--;
    tabs.push({ name: sh.getName(), cc: tm[1].toUpperCase(), kind: tm[2].toUpperCase().indexOf('OG') === 0 ? 'OG' : 'PR', rows: vals.slice(0, last) });
  });
  if (!tabs.length) throw new Error('이 시트에서 MY_OG&TEST, MY_PR&BR 같은 국가 탭을 찾지 못했습니다 / Không tìm thấy tab quốc gia như MY_OG&TEST');
  return { title: title, period: [+pm[1], +pm[2], +pm[3], +pm[4]], tabs: tabs };
}

/** 드라이브의 양식 pptx. 큰 값을 한 번에 돌려주다 끊기지 않도록 조각(chunk)으로 나눠 보낸다.
 *  getTemplateInfo() → {name, size, mime, chunks} / getTemplateChunk(i) → base64 문자열. 오류는 던지지 않고 {error} 로 돌려준다. */
var TEMPLATE_CHUNK = 150000;   // 바이트
function templateFile_() {
  var id = props().getProperty('TEMPLATE_FILE_ID');
  if (!id) return null;
  return DriveApp.getFileById(id);
}
function getTemplateInfo() {
  try {
    var f = templateFile_(); if (!f) return null;
    var blob = f.getBlob(), size = blob.getBytes().length;
    return { name: f.getName(), size: size, mime: blob.getContentType(), chunks: Math.ceil(size / TEMPLATE_CHUNK) };
  } catch (e) { return { error: String(e && e.message || e) }; }
}
function getTemplateChunk(i) {
  try {
    var f = templateFile_(); if (!f) return { error: 'TEMPLATE_FILE_ID 없음' };
    var bytes = f.getBlob().getBytes(), start = i * TEMPLATE_CHUNK;
    return { i: i, b64: Utilities.base64Encode(bytes.slice(start, Math.min(bytes.length, start + TEMPLATE_CHUNK))) };
  } catch (e) { return { error: String(e && e.message || e) }; }
}
/** (하위 호환) 한 번에 전부 */
function getTemplate() {
  var f = templateFile_(); if (!f) return null;
  return { name: f.getName(), b64: Utilities.base64Encode(f.getBlob().getBytes()) };
}

/** 화면의 [진단] 버튼: 무엇이 안 되는지 글로 돌려준다 (토큰 값은 안 보여줌) */
function diagnose() {
  var p = props(), lines = [], id = p.getProperty('TEMPLATE_FILE_ID');
  lines.push('버전 ' + VERSION + ' / 사용자 ' + Session.getActiveUser().getEmail() + ' / 실행 계정 ' + Session.getEffectiveUser().getEmail());
  lines.push('TEMPLATE_FILE_ID: ' + (id ? '있음 (' + id.length + '자)' : '없음'));
  if (id) {
    try { var f = DriveApp.getFileById(id); var b = f.getBlob();
      lines.push('드라이브 양식: ' + f.getName() + ' / ' + b.getContentType() + ' / ' + b.getBytes().length + ' bytes' +
                 (b.getContentType().indexOf('presentationml') < 0 ? '  ← pptx 가 아님 (구글 슬라이드로 변환된 파일이면 원본 pptx 를 다시 올려야 함)' : '  ✓'));
    } catch (e) { lines.push('드라이브 양식 읽기 실패: ' + (e && e.message || e)); }
  }
  lines.push('META_ACCESS_TOKEN: ' + (p.getProperty('META_ACCESS_TOKEN') ? '있음' : '없음') + ' / 발급일 ' + (p.getProperty('META_TOKEN_ISSUED') || '미기입'));
  ['MY', 'SG', 'ID', 'PH'].forEach(function (c) { var a = accounts_(p, c); if (a.length) lines.push('광고계정 ' + c + ': ' + a.length + '개'); });
  try { UrlFetchApp.fetch('https://graph.facebook.com/v21.0/', { muteHttpExceptions: true }); lines.push('외부 연결(UrlFetch): ✓'); }
  catch (e) { lines.push('외부 연결(UrlFetch) 실패: ' + (e && e.message || e)); }
  return lines.join('\n');
}

// ---------------- Meta 이미지 수집 (src/meta_api.py 의 선택 규칙 그대로)
/** 국가의 광고계정 목록 ['act_123', ...]. 속성 값은 쉼표·공백·세미콜론으로 여러 개 가능 */
function accounts_(p, cc) {
  return String(p.getProperty('META_AD_ACCOUNT_ID_' + String(cc || '').toUpperCase()) || '').split(/[,\s;]+/).filter(Boolean)
    .map(function (a) { return 'act_' + a.replace(/^act_/, ''); });
}
function graphGet_(path, params, token) {
  var q = Object.keys(params).map(function (k) { return k + '=' + encodeURIComponent(params[k]); }).join('&');
  var res, body;
  for (var attempt = 0; attempt < 4; attempt++) {
    res = UrlFetchApp.fetch(GRAPH + path + '?' + q, { headers: { Authorization: 'Bearer ' + token }, muteHttpExceptions: true });
    body = JSON.parse(res.getContentText() || '{}');
    var code = body.error && body.error.code;
    if (res.getResponseCode() < 400 && !body.error) return body;
    if ([4, 17, 32, 613].indexOf(code) >= 0 || [429, 500, 502, 503].indexOf(res.getResponseCode()) >= 0) { Utilities.sleep(2000 * Math.pow(2, attempt)); continue; }
    break;
  }
  var msg = body.error ? ('(' + body.error.code + ') ' + body.error.message) : ('HTTP ' + res.getResponseCode());
  throw new Error('Meta API 오류 ' + String(msg).split(token).join('***').slice(0, 300));
}
function adDates_(name) {
  var m = /_(\d{6})_(\d{6}|NONE)$/.exec(name || ''); if (!m) return null;
  function d(s) { var dt = new Date(Date.UTC(2000 + +s.slice(0, 2), +s.slice(2, 4) - 1, +s.slice(4, 6))); return isNaN(dt.getTime()) ? null : dt; }
  var a = d(m[1]); if (!a) return null;
  return [a, m[2] === 'NONE' ? null : d(m[2])];
}
function overlaps_(name, period) {
  var d = adDates_(name); if (!d || !period) return null;
  return d[0] <= period[1] && (d[1] === null || d[1] >= period[0]);
}
function pickAd_(ads, name, period) {
  var best = null, bs = null;
  ads.forEach(function (a) {
    var n = a.name || '', d = adDates_(n);
    var s = [n.toLowerCase().indexOf(name.toLowerCase()) === 0 ? 1 : 0, overlaps_(n, period) === true ? 1 : 0, a.effective_status === 'ACTIVE' ? 1 : 0,
             (a.creative && a.creative.image_url) ? 1 : 0, d ? d[0].getTime() : 0];
    if (!bs || s.some(function (v, i) { return v !== bs[i] && v > bs[i] && s.slice(0, i).every(function (w, j) { return w === bs[j]; }); })) { best = a; bs = s; }
  });
  return best;
}
/** period: [시작 'YYYY-MM-DD', 끝 'YYYY-MM-DD'] (브라우저가 시트 제목의 기간으로 계산). 반환: {found, adName, kind, mime, b64} */
function fetchImage(country, creativeName, period) {
  var p = props(), token = p.getProperty('META_ACCESS_TOKEN'), accts = accounts_(p, country);
  if (!token) throw new Error('토큰이 없습니다 (META_ACCESS_TOKEN)');
  if (!accts.length) throw new Error(country + ' 광고계정 ID 가 없습니다 (META_AD_ACCOUNT_ID_' + country + ')');
  var per = period ? [new Date(period[0] + 'T00:00:00Z'), new Date(period[1] + 'T00:00:00Z')] : null;
  var fields = 'name,effective_status,creative.thumbnail_width(1080).thumbnail_height(1080){image_url,thumbnail_url,video_id}';
  var params = { fields: fields, limit: 25, filtering: JSON.stringify([{ field: 'name', operator: 'CONTAIN', value: creativeName }]), effective_status: JSON.stringify(STATUSES) };
  var ads = [], errors = [];
  accts.forEach(function (acct) {   // 계정이 여러 개(ID: Shopee + Tokopedia)면 모두 검색해 합친다
    try { ads = ads.concat(graphGet_(acct + '/ads', params, token).data || []); } catch (e) { errors.push(acct + ': ' + e.message); }
  });
  if (errors.length && !ads.length && errors.length === accts.length) throw new Error(errors.join(' / '));
  var ad = pickAd_(ads, creativeName, per);
  if (!ad) return { found: false, candidates: 0 };
  var cr = ad.creative || {}, url = null, kind = null;
  if (cr.image_url) { url = cr.image_url; kind = 'image_url'; }
  else if (cr.video_id) { try { var th = graphGet_(cr.video_id + '/thumbnails', { fields: 'uri,is_preferred,width,height' }, token).data || [];
      var pref = th.filter(function (x) { return x.is_preferred; }); var b = pref[0] || th.sort(function (x, y) { return (y.width || 0) * (y.height || 0) - (x.width || 0) * (x.height || 0); })[0];
      if (b && b.uri) { url = b.uri; kind = 'video_thumbnail'; } } catch (e) { /* 권한 부족이면 기본 썸네일로 */ } }
  if (!url && cr.thumbnail_url) { url = cr.thumbnail_url; kind = 'thumbnail_url'; }
  if (!url) return { found: false, candidates: (body.data || []).length, adName: ad.name };
  var img = UrlFetchApp.fetch(url, { muteHttpExceptions: true });   // CDN 주소에는 토큰을 보내지 않는다
  if (img.getResponseCode() >= 400) throw new Error('이미지 다운로드 실패 HTTP ' + img.getResponseCode());
  return { found: true, adName: ad.name, kind: kind, mime: img.getHeaders()['Content-Type'] || 'image/jpeg', b64: Utilities.base64Encode(img.getContent()) };
}
