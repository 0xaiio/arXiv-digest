# -*- coding: utf-8 -*-
"""2026-09-18 批次：把本期新增论文的中文摘要合并进 output/summaries.json。

key 一律 arXiv 短号（不带版本、不带分类前缀）。只新增，不覆盖已有条目。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")
PATH = os.path.join(OUT, "summaries.json")

NEW = {
    "2609.20069": "系统刻画 DAG 型 BFT 共识上的 MEV 攻击谱系（竞争、合谋、腐败）：所有副本并发出块放大了提议者对交易顺序的自由裁量权，论文梳理攻击面并量化其对公平性的影响。",
    "2609.19893": "指出即便使用精确无界计数器，延迟均衡攻击（用长良性前缀掩盖后续的对抗性频率偏移）仍能攻破现有频率感知去偏；提出有界内存的 Hopper 协议，据去偏所需的流估计性质选用 sketch 结构。",
    "2609.19583": "用大语言模型自动生成 Lean 证明来做 LLVM 翻译验证，把 Alive2 基于 SMT 的有界保证扩展到符号位宽与循环等其难以覆盖的场景，大幅压缩交互式定理证明所需的人工证明工程。",
    "2609.19391": "MAGS 多智能体框架让编码智能体在生成可执行程序的同时自动产出形式化规约与安全证明，以机器可校验的保证弥补模糊测试、静态分析与 LLM-as-Verifier 在边界情形覆盖上的不足。",
    "2609.18778": "研究「接收方选择性静默」这一能规避现有全部追责机制的活性攻击：证明单个攻击者对至多 f 个诚实节点静默时与诚实节点不可区分，从而给出静默识别下界 K_SI ≥ f+1，并据此设计可追责的活性保障。",
    "2609.18563": "提出协作式拜占庭容错对等采样 AUPE，抵御恶意节点通过抬高自身在诚实节点视图中所占比例来操纵成员感知、进而破坏上层协议的攻击。",
    "2609.18512": "PatchyBFT 用大语言模型从一份参考实现自动生成多样化的容错协议副本实现，以缓解「所有副本共享同一份实现」带来共性缺陷、从而击穿容错阈值这一风险。",
    "2609.17645": "把持久执行框架的权威日志从托管方单点持有改为多方复制的认证追加日志：运行由单写者 epoch core 串接而成，执行者交接由法定人数终结的闭包证书裁定，实现无「房东」的工作流状态复制。",
    "2609.19325": "AUDITPLAN 让模型先输出结构化安全计划（威胁标签、预期动作、显式约束）再据此作答，使安全对齐可被机器审计，并能区分稳健拒答与「一律拒答」「表面安全套话」两类退化捷径。",
    "2609.18158": "XSplicer 以证据驱动方式在异构账本间重建跨链交易对应关系，摆脱对官方 API、EVM 特定假设与脆弱时序启发式的依赖；对 131 座桥的调查显示仅 16.79% 提供完整公开追踪。",
    "2609.17902": "刻画非托管预测市场「链下撮合 + 链上结算」之间的原子性缺口：链下接受或撮合时有效的订单可能在链上结算前失效，形成 ghost-filled orders，并给出针对性的检测与测试方法。",
}


def main():
    data = {}
    if os.path.exists(PATH):
        data = json.load(open(PATH, encoding="utf-8"))
    before = len(data)
    added = 0
    for k, v in NEW.items():
        if k not in data or not data[k]:
            data[k] = v
            added += 1
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("summaries: %d -> %d (added %d)" % (before, len(data), added))


if __name__ == "__main__":
    main()
