#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性脚本：把 Hagit Attiya 的画像并入 interests.json（可重复执行，幂等）。"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "interests.json")

ATTIYA_TOPICS = [
    {
        "name": "共享内存与线性一致性",
        "weight": 0.95,
        "keywords": [
            "linearizability", "linearizable", "strong linearizability",
            "sequential consistency", "sequentially consistent",
            "quiescent consistency", "shared memory", "shared-memory",
            "distributed shared memory", "atomic register", "atomic registers",
            "register", "registers", "single-writer", "multi-writer",
            "snapshot object", "compare-and-swap", "compare and swap", "CAS",
            "fetch-and-add", "test-and-set", "read-write", "read/write",
            "wait-free", "waitfree", "lock-free", "lockfree", "non-blocking",
            "obstruction-free", "universal construction", "helping",
            "consensus number", "consensus hierarchy", "step complexity",
            "remote memory reference", "RMRs", "RMR", "local spinning",
            "renaming", "concurrent object", "concurrent objects",
            "concurrent data structure", "concurrent data structures",
            "concurrent priority queue", "concurrent queue", "concurrent stack",
            "contention", "shared object", "shared objects",
            "atomic snapshot", "immediate snapshot", "iterated immediate snapshot",
        ],
    },
    {
        "name": "事务内存与同步原语",
        "weight": 0.9,
        "keywords": [
            "transactional memory", "software transactional memory", "STM",
            "hardware transactional memory", "HTM", "opacity", "TMS1", "TMS2",
            "virtual worlds", "transactional", "abort", "aborted", "rollback",
            "read set", "write set", "validation", "commit",
            "synchronization primitive", "synchronization primitives",
            "mutex", "mutual exclusion", "spin lock", "spinlock", "locking",
            "lock", "locks", "reader-writer lock", "barrier", "semaphore",
            "monitor", "atomicity", "atomic block", "linearizable object",
            "strict serializability", "commit order",
        ],
    },
    {
        "name": "分布式下界与不可能性",
        "weight": 0.85,
        "keywords": [
            "impossibility", "impossible", "lower bound", "lower bounds",
            "tight bound", "tight bounds", "upper bound", "upper bounds",
            "FLP", "k-set agreement", "set agreement", "colorless task",
            "adversary", "adversarial", "message complexity",
            "round complexity", "space complexity", "time complexity",
            "failure detector", "failure detectors", "partial synchrony",
            "asynchronous", "asynchrony", "synchronous", "synchrony",
            "crash failure", "crash failures", "Byzantine", "Byzantine fault",
            "t-resilient", "resilience", "solvability", "solvable", "unsolvable",
            "computability", "decision task", "heard-of", "heard of model",
            "wait-free hierarchy", "message-passing", "message passing",
            "shared-memory model", "atomicity failure", "indistinguishability",
        ],
    },
    {
        "name": "时序随机化与性能分析",
        "weight": 0.7,
        "keywords": [
            "timing-based", "timeout", "timeouts", "timing assumptions",
            "randomized", "randomization", "randomized algorithm",
            "probabilistic", "expected time", "expected step",
            "latency", "tail latency", "throughput", "performance analysis",
            "queuing", "queueing", "response time", "work-stealing",
            "load balancing", "scheduling", "amortized", "scalability",
            "benchmark", "evaluation", "staleness", "freshness",
        ],
    },
]

ATTIYA_PEOPLE = [
    "Constantin Enea", "Constantin Enea", "Armando Castaneda", "Armando Castañeda",
    "Rotem Oshman", "Noa Schiller", "Alessia Milani", "Keren Censor-Hillel",
    "Danny Hendler", "Jennifer Welch", "Gadi Taubenfeld", "Petr Kuznetsov",
    "Rachid Guerraoui", "Antonio Fernandez Anta", "Antonio Fernández Anta",
    "Eli Gafni", "Faith Ellen", "Panagiota Fatourou", "Sergio Rajsbaum",
    "Michel Raynal", "Andreia Mordido",
]

ATTIYA_SYSTEMS = ["TraTM", "NOrec", "TL2", "SkySTM", "LSA", "P-SIM", "CCL"]


def main():
    d = json.load(open(PATH, encoding="utf-8"))
    names = {t["name"] for t in d["topics"]}

    d["_comment"] = ("个性化推荐画像。综合自 Hengfeng Wei 魏恒峰（湖南大学，"
                     "https://hengxin.github.io）、Alexey Gotsman（IMDEA Software Institute）"
                     "与 Hagit Attiya（Technion）的研究兴趣：数据库系统 / 分布式计算 / "
                     "形式化方法 / 共享内存并发 四者的交叉地带。")

    if not any("Attiya" in o.get("name", "") for o in d.get("owners", [])):
        d["owners"].append({
            "name": "Hagit Attiya",
            "site": "https://hagit.net.technion.ac.il/",
            "affiliation": "Technion — Israel Institute of Technology, Faculty of Computer Science",
            "interests": ("Distributed and parallel computing: synchronization primitives, "
                          "fault-tolerance, agreement problems, randomization, timing-based "
                          "algorithms; transactional memory; performance analysis"),
            "signature_topics": [
                "共享内存计算：线性一致性 / 强线性一致性、wait-free 与 lock-free 并发数据结构与步进复杂度下界",
                "事务内存的规约与可组合性（opacity / TMS）、同步原语与仲裁（arbitration）",
                "分布式计算的不可能性与下界：集合协商、无色任务、heard-of 模型、消息传递与共享内存的等价分离",
                "时序与随机化算法、容错与故障检测器、分布式服务器性能分析",
            ],
        })

    for t in ATTIYA_TOPICS:
        if t["name"] in names:
            continue
        d["topics"].append(t)

    seen = set(d.get("people", []))
    for p in ATTIYA_PEOPLE:
        if p not in seen:
            d["people"].append(p)
            seen.add(p)
    seen = set(d.get("signature_systems", []))
    for s in ATTIYA_SYSTEMS:
        if s not in seen:
            d["signature_systems"].append(s)
            seen.add(s)

    # 行为学习参数（供 profile.py 读取，可手工调整）
    d.setdefault("behavior", {
        "actions": {
            "favorite": 1.0, "unfavorite": -0.7, "download": 1.3,
            "pdf": 0.55, "abstract": 0.3, "downvote": -1.6, "undownvote": 0.9,
        },
        "lr_topic": 0.06, "lr_keyword": 0.05,
        "topic_range": [0.25, 3.0], "keyword_range": [-4.0, 4.0],
        "downvote_paper_penalty": -12.0,
    })

    # 学习率：保证单次点击就能看到推荐列表的变化
    d["behavior"]["lr_topic"] = 0.15
    d["behavior"]["lr_keyword"] = 0.12

    # 微调：负向主题加强；去掉过于宽泛、会到处误命中的词
    d["negative"]["weight"] = -1.0
    generic = {"benchmark", "evaluation", "scalability"}
    for t in d["topics"]:
        if t["name"] == "时序随机化与性能分析":
            t["keywords"] = [k for k in t["keywords"] if k not in generic]
    for extra_kw in ["GUI testing", "mobile app", "SWE-bench", "SWE-Bench",
                     "code generation", "unit test generation", "bug detection benchmark"]:
        if extra_kw not in d["negative"]["keywords"]:
            d["negative"]["keywords"].append(extra_kw)

    json.dump(d, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("topics: %d, people: %d, owners: %d" % (
        len(d["topics"]), len(d["people"]), len(d["owners"])))


if __name__ == "__main__":
    main()
