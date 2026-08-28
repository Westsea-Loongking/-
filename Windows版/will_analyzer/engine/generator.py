# -*- coding: utf-8 -*-
"""意志生成器。

把结构化画像（核心需要 × 核心威胁 × 价值优先级 × 行动模式 × 关系策略 × 代价边界）
组合成一套"意志"：意志名、意志句、四条规则（趋近 / 拒绝 / 冲突 / 复归）、阴影、成长方向。
"""

from will_analyzer.data import dimensions as D


def generate(profile):
    """根据画像生成完整的意志模型。返回 dict。"""
    scores = profile["scores"]

    top_need_key = profile["needs"][0][0] if profile["needs"] else "need_autonomy"
    second_need = profile["needs"][1] if len(profile["needs"]) > 1 else None
    top_threat = profile["threats"][0] if profile["threats"] else None
    second_threat = profile["threats"][1] if len(profile["threats"]) > 1 else None
    top_value = profile["values"][0] if profile["values"] else None
    top_action = profile["actions"][0] if profile["actions"] else None
    top_rel = profile["rels"][0] if profile["rels"] else None

    need_def = D.CORE_NEEDS.get(top_need_key, D.CORE_NEEDS["need_autonomy"])
    value_def = D.VALUES.get(top_value[0], None) if top_value else None
    threat_def = D.CORE_THREATS.get(top_threat[0], None) if top_threat else None
    action_def = D.ACTION_MODES.get(top_action[0], None) if top_action else None
    rel_def = D.RELATIONSHIP_STRATEGIES.get(top_rel[0], None) if top_rel else None

    # 根据首要价值选择意志名的两种风格之一
    outward_values = {"val_freedom", "val_fairness", "val_achievement",
                      "val_exploration", "val_truth"}
    name_idx = 0 if (top_value and top_value[0] in outward_values) else 1
    will_name = need_def["names"][name_idx % len(need_def["names"])]

    # 意志句：首要需要 + 首要价值的叠加
    will_sentence = need_def["sentence"]
    if value_def:
        will_sentence = "{} {}" .format(need_def["sentence"], value_def["principle"])

    # 冲突规则：优先采用首要价值的冲突规则，否则回退到需要主题默认
    conflict_rule = value_def["conflict"] if value_def else None

    result = {
        "name": will_name,
        "sentence": will_sentence,
        "core_need": {
            "key": top_need_key,
            "label": need_def["label"],
            "blurb": need_def["blurb"],
        },
        "rules": {
            "approach": need_def["approach"],
            "refusal": need_def["refusal"],
            "conflict": conflict_rule,
            "recovery": need_def["recovery"],
        },
        "shadow": need_def["shadow"],
        "growth": need_def["growth"],
        "meta": {
            "need_key": top_need_key,
            "second_need": second_need,
            "threat": top_threat,
            "second_threat": second_threat,
            "value": top_value,
            "action": top_action,
            "rel": top_rel,
        },
    }

    # 阴影追加：由首要威胁带来的触发场景
    if threat_def:
        result["shadow"] = "{} 触发场景：{}".format(
            result["shadow"], threat_def["trigger"]
        )
        result["core_threat"] = {
            "key": top_threat[0],
            "label": threat_def["label"],
            "fear": threat_def["fear"],
            "trigger": threat_def["trigger"],
        }
    else:
        result["core_threat"] = None

    # 成长方向追加：结合行动模式与关系策略
    if action_def:
        result["growth"] = "{} 你习惯以「{}」的方式行动：{}".format(
            result["growth"], action_def["label"], action_def["how"]
        )
        result["action"] = {
            "key": top_action[0],
            "label": action_def["label"],
            "how": action_def["how"],
            "desc": action_def["desc"],
        }

    if rel_def:
        result["relationship"] = {
            "key": top_rel[0],
            "label": rel_def["label"],
            "desc": rel_def["desc"],
        }

    # 价值优先级列表
    result["values"] = []
    for vkey, vscore in profile["values"]:
        vdef = D.VALUES.get(vkey)
        if not vdef:
            continue
        result["values"].append({
            "key": vkey,
            "label": vdef["label"],
            "principle": vdef["principle"],
            "score": vscore,
        })

    # 边界与代价
    result["costs"] = []
    for ckey, cscore in profile["costs"]:
        cdef = D.COST_STANCES.get(ckey)
        if not cdef:
            continue
        result["costs"].append({
            "key": ckey,
            "label": cdef["label"],
            "desc": cdef["desc"],
            "score": cscore,
        })

    return result
