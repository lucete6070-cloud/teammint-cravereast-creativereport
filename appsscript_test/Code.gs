/**
 * Apps Script 시험용 서버 코드 (docs/AppsScript_시험_따라하기.md 의 순서대로 붙여넣기).
 * 토큰·광고계정 ID 는 "프로젝트 설정 > 스크립트 속성" 에만 넣는다. 코드·채팅·문서에 쓰지 않는다.
 *   META_ACCESS_TOKEN, META_AD_ACCOUNT_ID_MY, META_AD_ACCOUNT_ID_SG, META_AD_ACCOUNT_ID_ID, META_AD_ACCOUNT_ID_PH
 */
var GRAPH = 'https://graph.facebook.com/v21.0/';
var TAB = /^[A-Za-z]{2}_(OG&TEST|PR&BR)$/;

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index').setTitle('Creative Report 시험');
}

// T1. 누가 접속했나
function whoAmI() {
  return { email: Session.getActiveUser().getEmail() || '(이메일을 읽지 못함)', time: new Date().toISOString() };
}

// 스크립트 속성이 들어 있는지 (값은 절대 돌려주지 않음, 이름과 길이만)
function checkProps() {
  var p = PropertiesService.getScriptProperties();
  var names = ['META_ACCESS_TOKEN', 'META_AD_ACCOUNT_ID_MY', 'META_AD_ACCOUNT_ID_SG', 'META_AD_ACCOUNT_ID_ID', 'META_AD_ACCOUNT_ID_PH'];
  return names.map(function (n) { var v = p.getProperty(n); return { name: n, set: !!v, len: v ? v.length : 0 }; });
}

// T2. 시트 주소 → 국가 탭을 '표시된 값' 그대로 읽기
function readTabs(text) {
  var m = /\/spreadsheets\/d\/([A-Za-z0-9_-]+)/.exec(text || '');
  var id = m ? m[1] : (text || '').trim();
  if (!id) throw new Error('시트 주소를 붙여넣어 주세요');
  var ss = SpreadsheetApp.openById(id);
  var out = { title: ss.getName(), periodOk: /\(\d{2}\/\d{2}-\d{2}\/\d{2}\)/.test(ss.getName()), tabs: [] };
  ss.getSheets().forEach(function (sh) {
    if (!TAB.test(sh.getName())) return;
    var vals = sh.getDataRange().getDisplayValues();
    var samples = { won: null, pct: null, bool: null, na: null };
    var hi = 0, lo = 0;
    for (var r = 0; r < vals.length; r++) {
      for (var c = 0; c < vals[r].length; c++) {
        var v = vals[r][c];
        if (!samples.won && /^₩[\d,]+$/.test(v)) samples.won = v;
        if (!samples.pct && /^\d[\d,.]*%$/.test(v)) samples.pct = v;
        if (!samples.bool && (v === 'TRUE' || v === 'FALSE')) samples.bool = v;
        if (!samples.na && v === '#N/A') samples.na = v;
        if (v === 'TRUE') (c < 16 ? hi++ : lo++);
      }
    }
    out.tabs.push({ name: sh.getName(), rows: vals.length, cols: vals[0] ? vals[0].length : 0, samples: samples,
                    trueCount: hi + lo, head: vals.slice(0, 3).map(function (row) { return row.slice(0, 8); }) });
  });
  if (!out.tabs.length) throw new Error('MY_OG&TEST 같은 국가 탭을 찾지 못했습니다');
  return out;
}

// T3·T6. 소재명으로 광고를 찾아 이미지 1장 받아 브라우저로 넘기기 (토큰은 서버에만)
function metaTest(country, creativeName) {
  var p = PropertiesService.getScriptProperties();
  var token = p.getProperty('META_ACCESS_TOKEN');
  var acct = p.getProperty('META_AD_ACCOUNT_ID_' + String(country || '').toUpperCase());
  if (!token) throw new Error('스크립트 속성 META_ACCESS_TOKEN 이 비어 있습니다');
  if (!acct) throw new Error('스크립트 속성 META_AD_ACCOUNT_ID_' + country + ' 이 비어 있습니다');
  if (!creativeName) throw new Error('소재명을 입력해 주세요');
  var t0 = Date.now();
  var q = 'fields=' + encodeURIComponent('name,status,creative{image_url,thumbnail_url}') +
          '&filtering=' + encodeURIComponent(JSON.stringify([{ field: 'name', operator: 'CONTAIN', value: creativeName }])) +
          '&limit=50&access_token=' + encodeURIComponent(token);
  var res = UrlFetchApp.fetch(GRAPH + 'act_' + String(acct).replace(/^act_/, '') + '/ads?' + q, { muteHttpExceptions: true });
  var body = JSON.parse(res.getContentText());
  if (body.error) throw new Error('Meta 오류 ' + body.error.code + ': ' + String(body.error.message).replace(token, '***'));
  var ads = body.data || [];
  var pick = null;
  for (var i = 0; i < ads.length; i++) {
    var cr = ads[i].creative || {};
    if (cr.image_url || cr.thumbnail_url) { pick = ads[i]; break; }
  }
  var t1 = Date.now();
  if (!pick) return { found: false, candidates: ads.length, searchMs: t1 - t0 };
  var url = pick.creative.image_url || pick.creative.thumbnail_url;
  var img = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  var bytes = img.getContent();
  var t2 = Date.now();
  return { found: true, candidates: ads.length, adName: pick.name, status: pick.status,
           kind: pick.creative.image_url ? 'image_url' : 'thumbnail_url',
           searchMs: t1 - t0, downloadMs: t2 - t1, bytes: bytes.length,
           mime: img.getHeaders()['Content-Type'] || 'image/jpeg', b64: Utilities.base64Encode(bytes) };
}
