#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径的唯一权威定义（单一职责：只回答「某个文件在哪」，不做任何 IO）。

为什么单独一个模块
------------------
各业务模块此前各自写 ``os.path.join(HERE, "output")``、``os.path.join(HERE,
"interests.json")`` …… 同一个约定散落在 10 个文件里。后果不是"不好看"，而是
真的出过事故：新增一个模块时忘了跟随既有的重定向约定，测试就把真实数据写坏了
（见 docs/contributing/testing.md「沙箱隔离」）。

集中到一处后：
  * 新增数据文件 → 只在这里加一行，所有模块自动一致；
  * 诊断环境问题 → ``python paths.py`` 一次列全，不用满仓库搜常量；
  * 测试要整体重定向 → 仍然按模块属性 monkeypatch（各模块保留同名常量），
    只是这些常量的**取值来源**变成了唯一的一处。

设计约束
--------
1. **不做缓存、不做 IO**：纯字符串计算。缓存会让「测试改了 ROOT 却拿到旧值」
   这类问题重新出现，而这正是本模块要消灭的问题。
2. **不 import 任何业务模块**：本模块是最底层，依赖方向只能是别人依赖它。
3. 顶层常量是为「按模块属性 monkeypatch」保留的兼容形态，业务代码也可以直接
   调函数（``config_path()``）拿到同样的值。
"""
import os

# 项目根：本文件所在目录。所有路径都相对它解析。
ROOT = os.path.dirname(os.path.abspath(__file__))


def under_root(*parts):
    """拼一个项目内路径。等价于 os.path.join(ROOT, *parts)，但语义更明确。"""
    return os.path.join(ROOT, *parts)


def output_dir():
    """运行产物目录（日报、缓存、归档库）。已被 .gitignore 排除。"""
    return under_root("output")


def config_path():
    """个人配置（含本机下载目录），运行时生成，不入库。"""
    return under_root("config.json")


def config_example():
    """配置模板：新用户首次运行时按它初始化 config.json。"""
    return under_root("config.example.json")


def interests_path():
    """个人兴趣画像（主题 / 熟悉研究者 / 画像主来源），运行时生成，不入库。"""
    return under_root("interests.json")


def interests_example():
    """画像模板：新用户首次运行时按它初始化 interests.json。"""
    return under_root("interests.example.json")


def library_path():
    """收藏 / 下载 / Downvote 的本地库。"""
    return os.path.join(output_dir(), "library.json")


def profile_state_path():
    """行为学习累计出的画像状态（主题倍率 / 关键词权重 / 论文罚分）。"""
    return os.path.join(output_dir(), "profile_state.json")


def behavior_path():
    """原始行为流水（append-only，用于复盘与迁移）。"""
    return os.path.join(output_dir(), "behavior.json")


def archive_db_path():
    """期次与「已见论文」的 SQLite 库。"""
    return os.path.join(output_dir(), "archive.db")


def archive_dir():
    """往期日报快照目录（只增不改）。"""
    return os.path.join(output_dir(), "archive")


def netroute_cache_path():
    """下载路由探测结果的持久化缓存。"""
    return os.path.join(output_dir(), "netroute.json")


def affiliations_path():
    """作者单位缓存（arXiv HTML 抽取结果）。"""
    return os.path.join(output_dir(), "affiliations.json")


def interests_extra_path():
    """『兴趣来源』及其解析增量（output 下，属运行产物）。"""
    return os.path.join(output_dir(), "interests_extra.json")


def packs_dir():
    """私人数据包的根目录：每个包是它的一个子目录（纯 JSON 文本）。

    与运行态的区别见 docs/architecture/data-isolation.md：包只在显式导入时被读取，
    运行期任何页面都不解析它的内容。
    """
    return under_root("presets")


# ---------------------------------------------------------------- 兼容常量
# 业务模块把各自的路径常量取自这里（``OUT = paths.OUT``）。保留模块级常量是
# 为了兼容既有的 monkeypatch 重定向方式，语义与直接调上面的函数完全一致。
OUT = output_dir()
CONFIG_PATH = config_path()
CONFIG_EXAMPLE = config_example()
INTERESTS = interests_path()
INTERESTS_EXAMPLE = interests_example()
LIB_PATH = library_path()
PROFILE_STATE_PATH = profile_state_path()
BEHAVIOR_PATH = behavior_path()
ARCHIVE_DB_PATH = archive_db_path()
ARCHIVE_DIR = archive_dir()
NETROUTE_CACHE_PATH = netroute_cache_path()
AFFILIATIONS_PATH = affiliations_path()
INTERESTS_EXTRA_PATH = interests_extra_path()
PACKS = packs_dir()


def snapshot():
    """当前全部路径的只读快照，供诊断输出与新模块查表用。"""
    return {name: globals()[name] for name in (
        "ROOT", "OUT", "CONFIG_PATH", "CONFIG_EXAMPLE",
        "INTERESTS", "INTERESTS_EXAMPLE", "LIB_PATH", "PROFILE_STATE_PATH",
        "BEHAVIOR_PATH", "ARCHIVE_DB_PATH", "ARCHIVE_DIR",
        "NETROUTE_CACHE_PATH", "AFFILIATIONS_PATH", "INTERESTS_EXTRA_PATH",
        "PACKS")}


def main():
    """``python paths.py``：列出全部路径并标出是否存在。"""
    rows = snapshot()
    width = max(len(k) for k in rows)
    print("项目根：%s\n" % rows["ROOT"])
    for name in rows:
        if name == "ROOT":
            continue
        val = rows[name]
        mark = "OK " if os.path.exists(val) else "-- "
        print("%s %-*s  %s" % (mark, width, name, val))
    print("\nOK = 已存在，-- = 尚未生成（首次运行会自动创建）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
