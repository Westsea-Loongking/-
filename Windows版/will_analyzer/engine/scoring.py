# -*- coding: utf-8 -*-
"""评分引擎。

负责把用户的作答（Likert 5 点 + 二选一）映射到各维度的得分，
并计算核心需要、核心威胁、价值优先级、行动模式、关系策略、世界假设等。
"""

from will_analyzer.data.questions import LIKERT_QUESTIONS, CHOICE_QUESTIONS


def _empty_scores():
    return {"total": 0.0, "count": 0.0}


def score(answers):
    """根据答案计算各维度得分。

    answers: dict，键为题目 id（int），值：
        - Likert 题：1~5 的整数
        - 选择题：'A' 或 'B'
    """
    dims = {}
    for q in LIKERT_QUESTIONS:
        qid = q["id"]
        val = answers.get(qid)
        if val is None or not isinstance(val, int):
            continue
        val = max(1, min(5, val))
        for d in q["dims"]:
            dct = dims.setdefault(d, _empty_scores())
            dct["total"] += val
            dct["count"] += 1

    for q in CHOICE_QUESTIONS:
        qid = q["id"]
        val = answers.get(qid)
        if val not in ("A", "B"):
            continue
        for d in q[val + "_dims"]:
            dct = dims.setdefault(d, _empty_scores())
            dct["total"] += 5  # 冲突题选中的价值记满分 5
            dct["count"] += 1

    # 归一化到 1~5 的均值
    result = {}
    for key, dct in dims.items():
        result[key] = round(dct["total"] / dct["count"], 3) if dct["count"] else 0.0
    return result


def top_keys(scores, keys, n):
    """返回指定键集合中得分最高的 n 个键（按分数降序，平局保留原顺序）。"""
    scored = [(k, scores.get(k, 0.0)) for k in keys if k in scores]
    scored.sort(key=lambda kv: kv[1], reverse=True)
    return scored[:n]


def extract_profile(scores):
    """从原始维度得分中提取结构化画像。"""
    from will_analyzer.data import dimensions as D

    needs = top_keys(scores, list(D.CORE_NEEDS.keys()), 3)
    threats = top_keys(scores, list(D.CORE_THREATS.keys()), 3)
    values = top_keys(scores, list(D.VALUES.keys()), 3)
    actions = top_keys(scores, list(D.ACTION_MODES.keys()), 2)
    rels = top_keys(scores, list(D.RELATIONSHIP_STRATEGIES.keys()), 2)

    cost_keys = list(D.COST_STANCES.keys())
    costs = top_keys(scores, cost_keys, 2)

    beliefs = {}
    for bkey, bdef in D.BELIEFS.items():
        raw = scores.get(bkey)
        if raw is None:
            continue
        # 反向计分项（如"世界防御性"）：高分意味着防御/不信任，展示时反转措辞
        beliefs[bkey] = {
            "score": raw,
            "inverted": bdef.get("inverted", False),
        }

    return {
        "scores": scores,
        "needs": needs,
        "threats": threats,
        "values": values,
        "actions": actions,
        "rels": rels,
        "costs": costs,
        "beliefs": beliefs,
    }


def detect_tensions(profile):
    """检测作答中的"内在张力"（矛盾点）。这些矛盾不是噪声，而是个性化素材。"""
    scores = profile["scores"]
    tensions = []

    def q_choice(qid):
        return None  # 由调用方传入选择结果

    # 自主高分 + 第 41 题选择干预（安全/守护）
    if scores.get("need_autonomy", 0) >= 3.5 and profile.get("q41") == "B":
        tensions.append(
            "你重视自己的自主，却在守护他人时倾向干预。你允许自己拥有的自由，未必愿意同样交到他人手上。"
        )
    # 重视真相 + 第 42 题选择延迟公开
    if scores.get("val_truth", 0) >= 3.5 and profile.get("q42") == "B":
        tensions.append(
            "你并非否定真相，而是更看重真相公开的时机与承受条件——真相重要，但“让真相不造成二次伤害”同样重要。"
        )
    # 公平需要高 + 第 44 题选择保护亲近的人
    if scores.get("need_fairness", 0) >= 3.5 and profile.get("q44") == "B":
        tensions.append(
            "你反感不公，但当犯错的是亲近之人时，你更想先帮助对方补救。公平的尺度，在你的亲密关系面前会有所软化。"
        )
    # 联结需要高 + 第 46 题选择止损退出
    if scores.get("need_connection", 0) >= 3.5 and profile.get("q46") == "B":
        tensions.append(
            "你渴望联结，却在一再受伤后选择止损退出。对你而言，自我保护有时会压过修复关系的愿望。"
        )
    # 安全需要高 + 第 48 题选择激进变革
    if scores.get("need_safety", 0) >= 3.5 and profile.get("q48") == "B":
        tensions.append(
            "你平时重视安全与可预见，却在看到缺陷持续伤人时，愿意承担混乱也要改变。守护，有时会让你变得激进。"
        )
    # 联结需要高 + 第 47 题选择克制不表达
    if scores.get("need_connection", 0) >= 3.5 and profile.get("q47") == "B":
        tensions.append(
            "你渴望联结，却倾向克制自己的挽留，害怕自己的需要成为别人的负担。你把爱藏了起来，用沉默保护关系。"
        )
    # 原则驱动（守持）高 + 第 50 题选择主动更新
    if scores.get("action_hold", 0) >= 3.5 and profile.get("q50") == "B":
        tensions.append(
            "你强调原则与坚持，却愿意在承诺与当下价值观冲突时主动更新。你的守持，并非对旧承诺的盲目忠诚。"
        )
    # 成就高 + 第 51 题选择关系优先
    if scores.get("val_achievement", 0) >= 3.5 and profile.get("q51") == "B":
        tensions.append(
            "你追求成就，却在事业机会与重要关系冲突时，愿意放弃或缩小机会。真正不可替代的东西，你心里很清楚。"
        )

    return tensions


def set_choices(profile, answers):
    """把选择题结果写入 profile，供张力检测使用。"""
    for q in CHOICE_QUESTIONS:
        qid = q["id"]
        val = answers.get(qid)
        if val in ("A", "B"):
            profile["q%d" % qid] = val
    return profile
