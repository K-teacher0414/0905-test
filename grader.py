# -*- coding: utf-8 -*-
"""
자동 채점 로직

핵심 함수
---------
- contains_any(text, keywords): 텍스트에 키워드 묶음 중 하나라도 있으면 True
- check_groups(text, groups): 여러 그룹(각 그룹은 동의어 리스트)에 대해
  '그룹마다 하나 이상 포함'되어야 전체 통과 (그룹 내부는 OR, 그룹 간은 AND)
- extract_method_label / strip_label: 문장 끝 "(방법명)" 표기 추출/제거
- grade_item(): 문항1(빈칸), 문항2(방법 명칭 포함 문장), 문항3(시각/청각+효과)을
  공통 구조로 채점하는 범용 함수
"""

import re
from rubric import METHOD_KEYWORDS, NON_STANDARD_LABELS


def contains_any(text: str, keywords) -> bool:
    return any(k in text for k in keywords)


def check_groups(text: str, groups):
    """groups: [[동의어1, 동의어2, ...], [동의어...], ...]
    반환: (전체통과여부, 충족못한 그룹 리스트)
    """
    if not groups:
        return True, []
    missing = [g for g in groups if not contains_any(text, g)]
    return (len(missing) == 0), missing


def extract_method_label(text: str):
    """문장 끝의 '(방법명)' 표기를 추출. 없으면 None."""
    m = re.search(r"\(([^()]{1,10})\)\s*$", text.strip())
    return m.group(1).strip() if m else None


def strip_label(text: str) -> str:
    """문장 끝의 '(방법명)' 표기를 제거한 본문만 반환."""
    return re.sub(r"\([^()]{1,10}\)\s*$", "", text.strip()).strip()


def check_method_characteristics(label: str, body: str):
    """표기한 방법(label)의 특징적 표현이 본문(body)에 있는지 확인.
    표준 6가지 방법이 아니면 None(판정 불가)을 반환.
    """
    keywords = METHOD_KEYWORDS.get(label)
    if keywords is None:
        return None
    return contains_any(body, keywords)


def grade_item(text: str, config: dict, has_method_label: bool = False):
    """단일 항목(빈칸 / 문장 / 시각·청각 요소) 채점.

    config에서 사용하는 키:
      required            : [[동의어...], ...]  (필수, AND/OR 규칙)
      opposite            : [[반대개념 키워드...], ...] (오개념 방지)
      opposite_scene1     : [[장면1과 겹치는 키워드...], ...] (대비 실패 감지)
      direction_required  : [[결론 방향 키워드...], ...] (결론 방향 확인)
      allowed_methods     : [str, ...]  (문항2에서만 사용, 방법 명칭 검증)
      flag_label          : [str, ...]  (표준 방법이 아닌 명칭, 예: '비유')
    """
    raw = text or ""
    text = raw.strip()

    result = {
        "raw": raw,
        "label": None,
        "label_status": None,
        "missing_required": [],
        "opposite_hits": [],
        "scene1_hits": [],
        "missing_direction": [],
        "passed": False,
        "notes": [],
    }

    if not text:
        result["notes"].append("답안이 입력되지 않았습니다.")
        return result

    body = text
    if has_method_label:
        label = extract_method_label(text)
        body = strip_label(text)
        result["label"] = label

        allowed = config.get("allowed_methods", [])
        flagged = config.get("flag_label", [])

        if label is None:
            result["label_status"] = "미표기"
            result["notes"].append("문장 끝에 사용한 설명 방법 명칭을 괄호로 표기해야 합니다. 예: (정의)")
        elif label in flagged:
            result["label_status"] = "비표준 명칭"
            result["notes"].append(
                f"'{label}'은(는) 6가지 표준 설명 방법(정의/예시/인과/분석/비교와 대조/분류와 구분)에 "
                f"속하지 않습니다. 서술 구조상 가장 가까운 표준 방법으로 다시 표기해야 합니다."
            )
        elif label not in allowed:
            result["label_status"] = "권장 방법 아님"
            result["notes"].append(
                f"이 문항에서 권장/허용되는 방법은 [{', '.join(allowed)}] 입니다. "
                f"'{label}'은(는) 조건에 맞지 않을 수 있습니다."
            )
        else:
            char_ok = check_method_characteristics(label, body)
            if char_ok is True:
                result["label_status"] = "일치"
            elif char_ok is False:
                result["label_status"] = "불일치"
                result["notes"].append(
                    f"방법 명칭은 '{label}'로 표기했지만, 그 방법의 특징적 표현이 문장에서 "
                    f"뚜렷하게 드러나지 않습니다. (예: '비교와 대조'라면 '반면/차이/~와 달리' 등)"
                )
            else:
                result["label_status"] = "확인 불가"

    # 1) 필수 키워드(의미) 검사 - 용어 없이 의미만 있어도 인정되는 부분
    req_ok, missing = check_groups(body, config.get("required", []))
    result["missing_required"] = missing

    # 2) 오개념 방지 - 다른 개념(반대 방향)의 키워드가 섞였는지
    opp_groups = config.get("opposite", [])
    opp_hits = [g for g in opp_groups if contains_any(body, g)]
    result["opposite_hits"] = opp_hits
    if opp_hits:
        for g in opp_hits:
            result["notes"].append(
                f"다른 개념/반대 상황에 해당하는 표현({', '.join(g)})이 포함되어 오개념으로 의심됩니다."
            )

    # 3) 장면1과의 대비 실패 감지 (문항3 전용, 있을 때만)
    #    주의: "배경음악 없이", "기계음 대신" 처럼 대비를 설명하려고 장면1 표현을
    #    부정형으로 언급하는 경우가 많아, 이 항목은 '경고(참고)'로만 표시하고
    #    합격/불합격 판정에는 반영하지 않는다. (필수 키워드 충족 여부로 이미 충분히 걸러짐)
    scene1_groups = config.get("opposite_scene1", [])
    scene1_hits = [g for g in scene1_groups if contains_any(body, g)]
    result["scene1_hits"] = scene1_hits
    if scene1_hits:
        result["notes"].append(
            "참고: 장면1과 겹치는 단어가 감지되었습니다. '~없이', '~대신', '~와 달리'처럼 "
            "명확한 대비 표현과 함께 쓰였는지 검토해 보세요. (이 항목만으로 자동 오답 처리하지는 않음)"
        )

    # 4) 결론 방향 확인
    dir_groups = config.get("direction_required", [])
    dir_ok, dir_missing = check_groups(body, dir_groups)
    result["missing_direction"] = dir_missing
    if dir_groups and not dir_ok:
        result["notes"].append("조건에서 요구하는 결론 방향(예: '예술로 보기 어렵다')이 명확히 드러나지 않습니다.")

    # 종합 판정
    label_ok = True
    if has_method_label:
        label_ok = result["label_status"] in ("일치",)

    # scene1_hits는 경고성 참고 항목이므로 통과 여부 판정에는 포함하지 않는다.
    passed = req_ok and (not opp_hits) and dir_ok and label_ok
    result["passed"] = passed
    if req_ok and not missing:
        pass
    else:
        for g in missing:
            result["notes"].append(f"필수 내용 누락: [{' / '.join(g)}] 중 하나도 포함되지 않았습니다.")

    return result


def grade_q1(set_cfg: dict, answers: dict):
    """문항1(표 완성형) 채점. answers = {"㉠": 학생답, "㉡": ..., "㉢": ...}"""
    items_cfg = set_cfg["q1"]["items"]
    results = {}
    for key, cfg in items_cfg.items():
        ans = answers.get(key, "")
        results[key] = grade_item(ans, cfg, has_method_label=False)
        results[key]["label_text"] = cfg["label"]
        results[key]["model_answer"] = cfg["model_answer"]
    score = sum(1 for r in results.values() if r["passed"])
    return results, score, len(items_cfg)


def grade_q2(set_cfg: dict, part1_text: str, part2_text: str):
    """문항2(문장 이어쓰기형) 채점."""
    q2cfg = set_cfg["q2"]
    parts_cfg = q2cfg["parts"]
    r1 = grade_item(part1_text, parts_cfg["part1"], has_method_label=True)
    r2 = grade_item(part2_text, parts_cfg["part2"], has_method_label=True)
    r1["label_text"] = parts_cfg["part1"]["label"]
    r2["label_text"] = parts_cfg["part2"]["label"]
    r1["model_answer"] = parts_cfg["part1"]["model_answer"]
    r2["model_answer"] = parts_cfg["part2"]["model_answer"]

    cross_notes = []
    distinct_ok = True
    if q2cfg.get("must_differ", False):
        if r1["label"] and r2["label"]:
            distinct_ok = r1["label"] != r2["label"]
            if not distinct_ok:
                cross_notes.append(
                    f"(1)과 (2)에 동일한 설명 방법 '{r1['label']}'을(를) 사용했습니다. "
                    f"서로 다른 설명 방법을 사용해야 합니다."
                )
        else:
            distinct_ok = None  # 명칭 미표기 등으로 판단 불가

    results = {"part1": r1, "part2": r2}
    score = sum(1 for r in (r1, r2) if r["passed"])
    if distinct_ok is False:
        score = max(0, score - 1)  # 방법 중복 시 감점(설계자가 배점 정책에 맞게 조정 가능)
    max_score = 2
    return results, score, max_score, cross_notes, distinct_ok


def grade_q3(set_cfg: dict, visual, visual_effect, audio, audio_effect):
    """문항3(영상 기획안형) 채점."""
    parts_cfg = set_cfg["q3"]["parts"]
    inputs = {
        "visual": visual,
        "visual_effect": visual_effect,
        "audio": audio,
        "audio_effect": audio_effect,
    }
    results = {}
    for key, cfg in parts_cfg.items():
        r = grade_item(inputs[key], cfg, has_method_label=False)
        r["label_text"] = cfg["label"]
        r["model_answer"] = cfg["model_answer"]
        results[key] = r
    score = sum(1 for r in results.values() if r["passed"])
    return results, score, len(parts_cfg)
