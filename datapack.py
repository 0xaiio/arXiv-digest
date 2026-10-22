#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""私人数据包（data pack）：把「某个人的一整套设置与使用数据」当成一个可导入导出的
**文本单元**管理。

为什么需要这一层
----------------
个人数据此前分散在 `config.json`、`interests.json` 与 `output/*.json` 三处，隔离全靠
`.gitignore` 的命名约定：既没有"一份完整的可迁移单元"（`export` 只搬配置文件，收藏与
下载记录留在原地），也没有任何结构保证"新用户看不到别人的数据"。设计与取舍见
docs/architecture/data-isolation.md。

四条设计约束
------------
1. **只读写 JSON 文本**：不引入 zip / sqlite，改动能被 `git diff` 看懂。
2. **一个包 = 一个目录**（`presets/<名字>/`）：复制、删除、分发都是一个目录操作。
3. **导入默认是「补齐 / 合并」**：唯一的覆盖动作是 `core` 分组，且必须先备份；
   `usage` / `notes` 只做并集，永不清空本机数据。
4. **本模块不持有模块级路径常量**：`targets()` 在调用时从 `paperutil` / `customize` /
   `profile` 的模块常量解析，因此 `tests/conftest.py` 的 monkeypatch 重定向自动生效
   （早期模块把 `OUT = pu.OUT` 固化在模块级，测试写坏过真实数据，见 paths.py 注释）。
"""
import hashlib
import json
import os
import re
import time

import paths

# ---------------------------------------------------------------- 文件与分组
# 分组是导入语义的分界线，不只是"选择性导出"的标签：
#   core      整文件替换（默认拒绝覆盖，需 --force）
#   usage     并集合并（本机已有条目优先，因为本机路径才有效）
#   notes     并集合并（编辑性内容，同名保留本机）
#   learning  覆盖（唯一会覆盖本机学习结果的分组，默认不导入）
CORE = ("config.json", "interests.json")
USAGE = ("library.json",)
LEARNING = ("profile_state.json", "behavior.json")
# 摘要的中文译文与简介同属「编辑性内容」：都是人写/人校对的文字，导入只做并集。
NOTES = ("summaries.json", "abstracts_zh.json", "rec_notes.json", "highlights.json")
GROUPS = {"core": CORE, "usage": USAGE, "learning": LEARNING, "notes": NOTES}
GROUP_ORDER = ("core", "usage", "learning", "notes")
ALL_FILES = tuple(f for g in GROUP_ORDER for f in GROUPS[g])

DEFAULT_IMPORT = ("core", "usage", "notes")
DEFAULT_EXPORT = ("core",)

SCHEMA = 1
MANIFEST = "manifest.json"
META = "meta.json"          # 旧版包只有这个，继续读
README = "README.md"
LEGACY_DIR = "legacy"

# 包名白名单式校验：目录穿越、隐藏目录、盘符一律拒绝。
_BAD_NAME = re.compile(r"[\\/]|\.\.|^\.|^$")

_ABS_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|/home/|/Users/|~[\\/]|/root/)")

PACKS = paths.PACKS


# ---------------------------------------------------------------- 基础 IO

def packs_dir():
    """数据包根目录（读模块级 PACKS，便于测试重定向）。"""
    return PACKS


def valid_name(name):
    """包名是否合法：非空、无路径分隔符、无 `..`、不以 `.` 开头。"""
    return bool(name) and not _BAD_NAME.search(str(name))


def pack_path(name):
    if not valid_name(name):
        raise ValueError("非法的数据包名：%r" % (name,))
    return os.path.join(packs_dir(), str(name))


def _read_json(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _write_json(path, obj):
    """临时文件 + os.replace：半截写入不会留下坏 JSON。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _same_json(a, b):
    """按内容比较两个 JSON 文件（忽略缩进/键序）。任一侧读不出即视为不同。"""
    da, db = _read_json(a, None), _read_json(b, None)
    if da is None or db is None:
        return False
    return json.dumps(da, ensure_ascii=False, sort_keys=True) == \
        json.dumps(db, ensure_ascii=False, sort_keys=True)


def _without_comment(obj):
    if isinstance(obj, dict):
        return {k: v for k, v in obj.items() if k != "_comment"}
    return obj


# 端口是**本机基础设施**（这台机器上服务监听哪），不属于"一个人的设置"：
# 它既不参与"是否仍是模板初值"的判定，也不会被导入覆盖 —— 否则导入一个包
# 会把服务悄悄挪到别人的端口上。见 _keep_local_port()。
_LOCAL_ONLY_KEYS = {"config.json": ("port",)}


def _comparable(fname, obj):
    """去掉注释与本机专属键，得到"可以跨机器比较"的形态。"""
    d = _without_comment(obj)
    if isinstance(d, dict):
        for k in _LOCAL_ONLY_KEYS.get(fname, ()):
            d.pop(k, None)
    return d


def _is_pristine(fname, dst):
    """本机文件是否**仍是模板初值**（用户还没在这上面花过工夫）。

    为什么要区分：新用户第一次打开页面就会生成 `config.json` / `interests.json`
    （模板的空骨架）。若不区分，界面上"一键导入"对**目标用户**永远失败——
    因为"本机已有不同内容"里的"不同"只是模板与包不一样，而模板并不是用户的劳动成果。
    判据用**与 `*.example.json` 完全一致（忽略 `_comment` 与本机专属键如 `port`）**：
    只要用户改过任何一项（类别、下载目录、主题……），就不再算初始状态，回到
    "默认拒绝、需 --force"的保守策略。
    """
    if fname not in CORE:
        return False
    example = {"config.json": paths.CONFIG_EXAMPLE,
               "interests.json": paths.INTERESTS_EXAMPLE}.get(fname)
    if not example or not os.path.exists(example) or not os.path.exists(dst):
        return False
    a, b = _read_json(dst, None), _read_json(example, None)
    if a is None or b is None:
        return False
    return json.dumps(_comparable(fname, a), ensure_ascii=False, sort_keys=True) == \
        json.dumps(_comparable(fname, b), ensure_ascii=False, sort_keys=True)


def _keep_local_port(dst, obj):
    """导入 config.json 时保留本机端口：端口不该被别人的包改掉。"""
    if not isinstance(obj, dict):
        return obj
    cur = _read_json(dst, {}) or {}
    port = cur.get("port") if isinstance(cur, dict) else None
    if isinstance(port, int):
        obj = dict(obj)
        obj["port"] = port
    return obj


def _group_of(fname):
    for g in GROUP_ORDER:
        if fname in GROUPS[g]:
            return g
    return ""


def _mtime_str(path):
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(path)))
    except OSError:
        return ""


# ---------------------------------------------------------------- 本机运行态

def targets():
    """包内文件名 -> 本机运行态路径。

    延迟导入 + 每次调用都取模块属性：测试用 monkeypatch 换掉
    `paperutil.CONFIG_PATH` / `customize.INTERESTS` / `profile.PROFILE_PATH` 后，
    这里立刻跟着变，不会读到真实数据。
    """
    import customize as CZ
    import paperutil as pu
    import profile as PF

    out = {
        "config.json": pu.CONFIG_PATH,
        "interests.json": CZ.INTERESTS,
        "library.json": pu.LIB_PATH,
        "profile_state.json": PF.PROFILE_PATH,
        "behavior.json": PF.BEHAVIOR_PATH,
    }
    for f in NOTES:
        out[f] = os.path.join(pu.OUT, f)
    return out


def state():
    """本机个人数据清单。**不返回绝对路径**：接口会原样给到浏览器，路径属本机信息。"""
    files = {}
    for fname, path in targets().items():
        exists = os.path.exists(path)
        files[fname] = {
            "group": _group_of(fname),
            "exists": exists,
            "bytes": os.path.getsize(path) if exists else 0,
            "updated_at": _mtime_str(path) if exists else "",
        }
    return {"files": files,
            "has_personal_data": any(v["exists"] for v in files.values())}


# ---------------------------------------------------------------- 包元信息

def manifest(name):
    """读清单；没有 manifest.json 时回落 meta.json（旧版包）。"""
    d = pack_path(name)
    m = _read_json(os.path.join(d, MANIFEST), None)
    if isinstance(m, dict):
        m.setdefault("name", name)
        m["_source"] = MANIFEST
        return m
    old = _read_json(os.path.join(d, META), {})
    old = dict(old) if isinstance(old, dict) else {}
    old.setdefault("name", name)
    old.setdefault("schema", 0)          # 0 = 旧版，无清单校验
    old["_source"] = META if old else ""
    return old


def _pack_files(name):
    d = pack_path(name)
    return [f for f in ALL_FILES if os.path.exists(os.path.join(d, f))]


def list_packs():
    """扫描包根目录。只返回"至少含一个已知文件"的目录。"""
    root = packs_dir()
    if not os.path.isdir(root):
        return []
    out = []
    for n in sorted(os.listdir(root)):
        if not valid_name(n):
            continue
        d = os.path.join(root, n)
        if not os.path.isdir(d):
            continue
        files = _pack_files(n)
        if not files:
            continue
        m = manifest(n)
        groups = {g: [f for f in files if f in GROUPS[g]] for g in GROUP_ORDER}
        out.append({
            "name": n, "path": d, "files": files,
            "groups": {g: v for g, v in groups.items() if v},
            "bytes": sum(os.path.getsize(os.path.join(d, f)) for f in files),
            "title": m.get("title") or "",
            "description": m.get("description") or "",
            "exported_at": m.get("exported_at") or "",
            "schema": int(m.get("schema") or 0),
            "has_manifest": bool(m.get("_source") == MANIFEST),
        })
    return out


def public_view(packs=None):
    """界面/接口用的**形状**视图：名称 + 文件清单 + 体积。

    刻意不含 title / description：那句描述往往就是作者的类别选择与研究方向，
    属要隔离的内容。规则见 docs/architecture/data-isolation.md §六。
    """
    packs = list_packs() if packs is None else packs
    return [{"name": p["name"], "files": p["files"], "groups": p["groups"],
             "bytes": p["bytes"]} for p in packs]


def compare_pack(name):
    """逐文件对比包与本机运行态（给 `tools/preset.py show` 用）。"""
    d = pack_path(name)
    tgt = targets()
    rows = []
    for f in _pack_files(name):
        src = os.path.join(d, f)
        dst = tgt[f]
        if not os.path.exists(dst):
            act = "new"              # 本机没有 → 会新增
        elif _same_json(src, dst):
            act = "same"             # 内容一致 → 跳过
        elif _is_pristine(f, dst):
            act = "pristine"         # 本机还是模板 → 直接替换
        else:
            act = "diff"             # 会合并 / 需 --force
        rows.append({"file": f, "group": _group_of(f), "bytes": os.path.getsize(src),
                     "status": act})
    return rows


# ---------------------------------------------------------------- 导入

def _backup(paths_):
    """把将要被覆盖的文件复制到 output/backup/<时间>/。返回 (目录, 文件名列表)。"""
    import paperutil as pu

    ts = time.strftime("%Y%m%d-%H%M%S")
    bdir = os.path.join(pu.OUT, "backup", ts)
    os.makedirs(bdir, exist_ok=True)
    done = []
    for p in paths_:
        if os.path.exists(p):
            dst = os.path.join(bdir, os.path.basename(p))
            with open(p, "rb") as fi, open(dst, "wb") as fo:
                fo.write(fi.read())
            done.append(os.path.basename(p))
    return bdir, done


def _merge_dict_file(dst, src_obj):
    """并集合并一个 {key: value} 形态的 JSON 文件（本机已有条目优先）。"""
    cur = _read_json(dst, {}) or {}
    if not isinstance(cur, dict):
        cur = {}
    added = 0
    for k, v in (src_obj or {}).items():
        if k not in cur:
            cur[k] = v
            added += 1
    _write_json(dst, cur)
    return added


def _merge_library(dst, src_obj):
    """library.json 专用合并：三个字典各取并集，本机同名条目一律保留。"""
    cur = _read_json(dst, {}) or {}
    cur.setdefault("favorites", {})
    cur.setdefault("downloads", {})
    cur.setdefault("downvotes", {})
    added = {}
    for sec in ("favorites", "downloads", "downvotes"):
        src = (src_obj or {}).get(sec) or {}
        n = 0
        for k, v in src.items():
            if k not in cur[sec]:
                cur[sec][k] = v
                n += 1
        added[sec] = n
    _write_json(dst, cur)
    return added


def _hash_ok(name, fname, path):
    """按清单校验 sha256。清单缺失或无该文件条目时视为通过（无法校验≠校验失败）。"""
    m = manifest(name)
    for item in (m.get("files") or []):
        if item.get("name") == fname and item.get("sha256"):
            return _sha256(path) == item["sha256"]
    return True


def import_pack(name, groups=None, force=False, dry_run=False):
    """把一个包导入本机运行态。返回 (ok, msg, report)。

    语义见模块文档与设计文档 §5.3：core 需 --force 才覆盖；usage/notes 只并集；
    learning 显式请求才写（并先备份）。
    """
    if not valid_name(name):
        return False, "非法的数据包名：%r" % (name,), []
    d = pack_path(name)
    if not os.path.isdir(d):
        avail = "、".join(p["name"] for p in list_packs()) or "无"
        return False, "找不到数据包：%s（可用：%s）" % (name, avail), []

    want = tuple(groups) if groups else DEFAULT_IMPORT
    bad = [g for g in want if g not in GROUPS]
    if bad:
        return False, "未知分组：%s（可选：%s）" % ("、".join(bad), "、".join(GROUP_ORDER)), []

    m = manifest(name)
    try:
        schema = int(m.get("schema") or 0)
    except Exception:  # noqa
        schema = 0
    if schema > SCHEMA:
        return False, ("数据包 %s 的清单版本是 %s，高于本程序支持的 %s；"
                       "请升级程序后再导入" % (name, schema, SCHEMA)), []

    files = [f for g in GROUP_ORDER if g in want for f in GROUPS[g]
             if os.path.exists(os.path.join(d, f))]
    if not files:
        return False, "数据包 %s 里没有可导入的文件（分组：%s）" % (name, "、".join(want)), []

    tgt = targets()
    report = []

    # ---- 第一轮：只做校验，任何"拒绝"在写盘之前就定下来 ----
    plan = []
    for f in files:
        src = os.path.join(d, f)
        group = _group_of(f)
        dst = tgt[f]
        row = {"file": f, "group": group, "action": "skipped", "reason": "",
               "bytes": os.path.getsize(src)}
        if _read_json(src, None) is None:
            row.update(action="refused", reason="包内 JSON 解析失败（未写入）")
            plan.append((f, src, dst, group, row))
            continue
        if not _hash_ok(name, f, src):
            row.update(action="refused",
                       reason="与 manifest.json 记录的 sha256 不符（包被手改过？）")
            plan.append((f, src, dst, group, row))
            continue
        exists = os.path.exists(dst)
        if group == "core":
            if not exists:
                row.update(action="written", reason="本机原本没有")
            elif _same_json(src, dst):
                row.update(action="skipped", reason="内容与本机一致")
            elif _is_pristine(f, dst):
                # 本机还是模板空骨架（新用户第一次打开就会生成它）：没有劳动成果可损失，
                # 直接替换。否则"一键导入"对目标用户永远失败，只能退回命令行 --force。
                row.update(action="replaced",
                           reason="本机仍是模板初值（未改过），直接写入")
            elif not force:
                row.update(action="refused",
                           reason="本机已有不同内容（加 --force 覆盖，会先备份）")
            else:
                row.update(action="replaced", reason="--force 覆盖（已备份）")
        elif group == "usage":
            row.update(action="merged" if exists else "written")
        elif group == "notes":
            row.update(action="merged" if exists else "written")
        elif group == "learning":
            row.update(action="replaced" if exists else "written",
                       reason="显式请求的行为学习数据（已备份）" if exists else "")
        plan.append((f, src, dst, group, row))

    # ---- 第二轮：需要覆盖的先备份；备份失败就不覆盖 ----
    to_backup = [dst for (_f, _s, dst, _g, row) in plan
                 if row["action"] == "replaced" and os.path.exists(dst)]
    backup_dir = ""
    if to_backup and not dry_run:
        try:
            backup_dir, _ = _backup(to_backup)
        except Exception as e:  # noqa
            for (_f, _s, dst, _g, row) in plan:
                if row["action"] == "replaced" and os.path.exists(dst):
                    row.update(action="refused", reason="备份失败，未覆盖：%s" % e)

    # ---- 第三轮：落盘 ----
    for (f, src, dst, group, row) in plan:
        act = row["action"]
        if dry_run or act in ("skipped", "refused"):
            report.append(row)
            continue
        try:
            if act == "written":
                obj = _read_json(src, None)
                if f == "config.json":
                    obj = _keep_local_port(dst, obj)
                _write_json(dst, obj)
            elif act == "replaced":
                obj = _read_json(src, None)
                if f == "config.json":
                    obj = _keep_local_port(dst, obj)
                _write_json(dst, obj)
            elif act == "merged":
                obj = _read_json(src, None)
                if group == "usage" and f == "library.json":
                    added = _merge_library(dst, obj)
                    row["reason"] = "并集：收藏 +%d、下载 +%d、Downvote +%d" % (
                        added["favorites"], added["downloads"], added["downvotes"])
                else:
                    n = _merge_dict_file(dst, obj)
                    row["reason"] = "并集：新增 %d 条" % n
            report.append(row)
        except Exception as e:  # noqa
            row.update(action="refused", reason="写入失败：%s" % e)
            report.append(row)

    refused = [r for r in report if r["action"] == "refused"]
    done = [r for r in report if r["action"] in ("written", "replaced", "merged")]
    parts = []
    if done:
        parts.append("已%s %d 个文件" % ("预演" if dry_run else "处理", len(done)))
    if refused:
        parts.append("%d 个文件未导入（%s）" % (
            len(refused), "；".join("%s：%s" % (r["file"], r["reason"]) for r in refused[:3])))
    if backup_dir and not dry_run:
        parts.append("原文件已备份到 output/backup/%s/" % os.path.basename(backup_dir))
    if not parts:
        parts.append("没有需要处理的文件")
    return (not refused), "，".join(parts), report


# ---------------------------------------------------------------- 导出

def _sanitize_config(obj):
    """把本机绝对下载目录换成中性的相对路径。"""
    cfg = dict(obj or {})
    d = str(cfg.get("download_dir") or "")
    if d and (os.path.isabs(d) or _ABS_PATH.match(d)):
        cfg["download_dir"] = "papers"
    return cfg


def _sanitize_library(obj):
    """下载记录只保留文件名：绝对路径换机器必然失效，也没必要公开。"""
    lib = json.loads(json.dumps(obj or {}))       # 深拷贝，别改到源对象
    for sec in ("favorites", "downloads"):
        for rec in (lib.get(sec) or {}).values():
            p = rec.get("path") if isinstance(rec, dict) else None
            if p:
                rec["path"] = os.path.basename(str(p))
    return lib


def scan_paths(obj, _prefix=""):
    """在 JSON 里找形似绝对路径的字符串（导出前的隐私自检）。"""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            hits += scan_paths(v, "%s.%s" % (_prefix, k) if _prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += scan_paths(v, "%s[%d]" % (_prefix, i))
    elif isinstance(obj, str) and _ABS_PATH.match(obj.strip()):
        hits.append("%s = %s" % (_prefix, obj[:80]))
    return hits


def export_pack(name, groups=None, sanitize=True, title="", description=""):
    """把本机运行态导出成一个包。返回 (ok, msg, report)。

    默认只导出 core：'随手 export 然后提交' 这个动作必须默认安全。
    """
    if not valid_name(name):
        return False, "非法的数据包名：%r" % (name,), []
    want = tuple(groups) if groups else DEFAULT_EXPORT
    bad = [g for g in want if g not in GROUPS]
    if bad:
        return False, "未知分组：%s（可选：%s）" % ("、".join(bad), "、".join(GROUP_ORDER)), []

    d = pack_path(name)
    tgt = targets()
    files = [f for g in GROUP_ORDER if g in want for f in GROUPS[g]
             if os.path.exists(tgt[f])]
    if not files:
        return False, ("本机没有可导出的文件（分组：%s）。首次运行后才有 config.json / "
                       "interests.json" % "、".join(want)), []

    os.makedirs(d, exist_ok=True)
    report, abs_hits = [], []
    for f in files:
        obj = _read_json(tgt[f], None)
        if obj is None:
            report.append({"file": f, "group": _group_of(f), "action": "refused",
                           "reason": "本机文件解析失败，跳过"})
            continue
        saved = obj
        if sanitize and f == "config.json":
            saved = _sanitize_config(obj)
        elif sanitize and f == "library.json":
            saved = _sanitize_library(obj)
        out = os.path.join(d, f)
        _write_json(out, saved)
        abs_hits += ["%s: %s" % (f, h) for h in scan_paths(saved)]
        report.append({"file": f, "group": _group_of(f), "action": "written",
                       "bytes": os.path.getsize(out), "reason": ""})

    old = manifest(name)
    man = {
        "schema": SCHEMA,
        "name": name,
        "title": title or old.get("title") or name,
        "description": description or old.get("description")
        or "由 `python tools/preset.py export %s` 导出" % name,
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "app": "arxiv-digest",
        "groups": [g for g in GROUP_ORDER if any(r["group"] == g for r in report)],
        "sanitized": bool(sanitize),
        "files": [{"name": r["file"], "group": r["group"],
                   "bytes": os.path.getsize(os.path.join(d, r["file"])),
                   "sha256": _sha256(os.path.join(d, r["file"]))}
                  for r in report if r["action"] == "written"],
    }
    _write_json(os.path.join(d, MANIFEST), man)

    msg = "已导出 %d 个文件到 %s" % (len(man["files"]), d)
    if abs_hits:
        msg += "；⚠ 仍存在形似绝对路径的内容 %d 处（%s）" % (
            len(abs_hits), "；".join(abs_hits[:3]))
    return True, msg, report
