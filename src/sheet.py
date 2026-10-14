"""시트 CSV 읽기 + 블록 파싱.

- CSV는 UTF-8(BOM 허용)로만 읽는다. 글자가 깨진 파일이면 EncodingProblem 으로 멈춘다.
- 숫자는 시트에 적힌 문자열 그대로 보관한다(재계산·반올림 없음).
"""
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

LEFT_COL = 1    # 좌측(ATC 또는 PR) 블록의 시작 열
RIGHT_COL = 16  # 우측(PUR 또는 BR) 블록의 시작 열
MAX_COLS = 32


class EncodingProblem(Exception):
    """CSV 글자가 깨졌거나 UTF-8이 아님."""


def read_csv(path):
    """UTF-8(BOM 허용)로 읽고 직사각형 리스트로 돌려준다. 깨진 글자면 EncodingProblem."""
    path = Path(path)
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise EncodingProblem(
            f"[멈춤] '{path.name}' 은(는) UTF-8 이 아닙니다 (바이트 위치 {e.start}). "
            "엑셀에서 'CSV UTF-8(쉼표로 분리)'로 다시 저장해 주세요.") from e
    if "�" in text:
        raise EncodingProblem(
            f"[멈춤] '{path.name}' 에 깨진 글자(�)가 있습니다. "
            "구글 시트에서 '파일 > 다운로드 > 쉼표로 구분된 값(.csv)'으로 다시 받아 주세요.")
    # 한글이 하나도 없는 경우(헤더가 항상 한글)도 비정상으로 본다.
    if not re.search(r"[가-힣]", text):
        raise EncodingProblem(f"[멈춤] '{path.name}' 에서 한글이 보이지 않습니다. 인코딩을 확인해 주세요.")
    rows = [r + [""] * (MAX_COLS - len(r)) for r in csv.reader(text.splitlines())]
    return rows


@dataclass
class Row:
    key: str            # 0열 보조키 (캠페인디테일+소재명)
    name: str           # 소재명
    cells: dict         # 지표 헤더 -> 시트 문자열
    hi: bool            # 고효율 소재 TRUE
    lo: bool            # 저효율 소재 TRUE
    memo: str = ""
    order: list = field(default_factory=list)  # 헤더 순서 (시트 열 순서)


@dataclass
class Block:
    side: str           # 'L' | 'R'
    detail: str         # 캠페인디테일 (UA, RT, Payday ...)
    campaign: str       # 캠페인명 (시트 값 그대로)
    rows: list          # 소재 행 (#N/A 제외)
    headers: list       # 지표 헤더 (지출금액 ... ROAS)
    na_only: bool = False   # 캠페인명/행이 전부 #N/A 인 블록
    note: str = ""      # 블록 상단 메모 (예: > 데이터 기간 점검 후 진행 예정)


def _is_na(v):
    return v.strip() in ("#N/A", "")


def parse_blocks(rows):
    """한 CSV(국가 탭 1개)의 좌·우 블록 전부."""
    blocks = []
    for side, st in (("L", LEFT_COL), ("R", RIGHT_COL)):
        for i, r in enumerate(rows):
            if r[st] != "TOP 10":
                continue
            hdr = []
            c = st + 1
            while c < MAX_COLS and r[c].strip():
                hdr.append(r[c].strip())
                c += 1
            # 마지막 두 개는 고효율/저효율 체크박스 열
            metrics = hdr[:-2]
            n = len(metrics)
            detail = rows[i - 2][st + 1].strip()
            campaign = rows[i - 1][st + 1].strip()
            note_cells = [x for x in rows[i - 1][st + 2: st + 14] if x.strip() and x.strip() != "* PPT 삽입 기준"]
            data = []
            for j in range(i + 1, min(i + 12, len(rows))):
                q = rows[j]
                if not q[st].strip() and not q[st + 1].strip():
                    break
                if q[st] == "TOP 10":
                    break
                if _is_na(q[st]):
                    continue
                cells = {metrics[k]: q[st + 1 + k] for k in range(n)}
                hi = q[st + 1 + n].strip().upper() == "TRUE"
                lo = q[st + 2 + n].strip().upper() == "TRUE"
                memo = q[st + 3 + n].strip() if st + 3 + n < MAX_COLS else ""
                data.append(Row(key=q[st - 1], name=q[st].strip(), cells=cells, hi=hi, lo=lo,
                                memo=memo, order=metrics))
            blocks.append(Block(side=side, detail=detail, campaign=campaign, rows=data, headers=metrics,
                                na_only=_is_na(campaign) and not data,
                                note=" ".join(x.strip() for x in note_cells)))
    return blocks


def load_tab(path):
    return parse_blocks(read_csv(path))
