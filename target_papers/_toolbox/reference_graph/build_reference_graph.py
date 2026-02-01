#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reference Graph MVP
===================

把某篇 survey 的 reference list（node 集合固定）建成 directed citation graph：
- Node = arxiv_metadata.json 裡的 metadata.key（bib key）
- Edge = A -> B（A cites B），只保留 B 也在 reference list 內的情況
- 視覺化 = 互動 HTML（pyvis + hierarchical layout），node 以 label 上色，預設不顯示文字

本工具刻意不做過度工程：
- 不解析 PDF
- 不引入資料庫（只用 JSON cache）
- 只用 Semantic Scholar Graph API（可用 arXiv/DOI/paperId/title 對應）

使用方式（repo root 執行）：
    python target_papers/_toolbox/reference_graph/build_reference_graph.py --slug <survey_slug>

輸入：
    workspaces/titlepaper_criteria_review/<slug>/harvest/arxiv_metadata.json

輸出：
    workspaces/titlepaper_criteria_review/<slug>/graph/
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import networkx as nx
import requests
from dotenv import load_dotenv
from pyvis.network import Network
from tqdm import tqdm

try:
    from rapidfuzz import fuzz  # type: ignore
except Exception:  # pragma: no cover
    fuzz = None


S2_BASE = "https://api.semanticscholar.org/graph/v1"


# -----------------------------
# 小工具：repo root / slug 路徑
# -----------------------------
def find_repo_root(start: Path) -> Path:
    """
    從 start 往上找，直到看到 workspaces/ 為止，視為 repo root。
    找不到就退回 start 的父層（保底）。
    """
    p = start.resolve()
    for parent in [p] + list(p.parents):
        if (parent / "workspaces").exists():
            return parent
    return start.resolve().parents[0]


def default_workspace_root(repo_root: Path) -> Path:
    return repo_root / "workspaces" / "titlepaper_criteria_review"


def default_metadata_json(workspace_root: Path, slug: str) -> Path:
    return workspace_root / slug / "harvest" / "arxiv_metadata.json"


def default_out_dir(workspace_root: Path, slug: str) -> Path:
    return workspace_root / slug / "graph"


def default_cache_dir(repo_root: Path) -> Path:
    return repo_root / "target_papers" / "_toolbox" / "reference_graph" / ".cache" / "semantic_scholar"


# -----------------------------
# 正規化 / 解析 DOI, arXiv
# -----------------------------
_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z]+(\[[^\]]*\])?(\{[^}]*\})?")
_BRACES_RE = re.compile(r"[{}]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """
    盡量把 bibtex/latex 風格 title 變成可比對的字串。
    目標不是 100% 正確，而是穩定、可維護。
    """
    if not title:
        return ""
    t = title.strip()

    # 常見 latex 指令粗略移除（保守）
    t = _LATEX_CMD_RE.sub(" ", t)

    # 去掉大括號（bibtex 常用來保留大小寫）
    t = _BRACES_RE.sub("", t)

    # 去掉多餘符號
    t = re.sub(r"[^0-9A-Za-z\u00C0-\u024F\u4e00-\u9fff\s\-:]", " ", t)

    t = t.lower()
    t = _WHITESPACE_RE.sub(" ", t).strip()
    return t


def looks_like_doi(s: str) -> bool:
    s = (s or "").strip()
    if not s:
        return False
    s = s.lower()
    return s.startswith("10.") or s.startswith("doi:10.")


def normalize_doi(doi: str) -> str:
    d = (doi or "").strip()
    d = d.replace("DOI:", "").replace("doi:", "").strip()
    return d.lower()


def extract_arxiv_id_from_any(x: Optional[str]) -> Optional[str]:
    if not x:
        return None
    s = x.strip()
    # 2301.12345v2 -> 2301.12345
    m = re.match(r"^(\d{4}\.\d{4,5})(v\d+)?$", s)
    if m:
        return m.group(1)
    # 可能已經是純 id
    return s


# -----------------------------
# 資料結構
# -----------------------------
@dataclasses.dataclass
class Node:
    key: str
    title: str
    label: str
    source: str = ""
    source_id: str = ""
    arxiv_id: str = ""
    doi: str = ""
    s2_paper_id: str = ""  # resolved S2 paperId（若成功）


@dataclasses.dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    match_type: str


# -----------------------------
# Cache + HTTP
# -----------------------------
class JsonFileCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_to_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        p = self._key_to_path(key)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def set(self, key: str, payload: Dict[str, Any]) -> None:
        p = self._key_to_path(key)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def stable_request_key(method: str, url: str, params: Optional[Dict[str, Any]], json_body: Any) -> str:
    # params 排序後做成穩定字串
    items = []
    if params:
        for k in sorted(params.keys()):
            v = params[k]
            items.append(f"{k}={v}")
    p = "&".join(items)
    jb = ""
    if json_body is not None:
        try:
            jb = json.dumps(json_body, sort_keys=True, ensure_ascii=False)
        except Exception:
            jb = str(json_body)
    raw = f"{method.upper()} {url}?{p} BODY:{jb}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def request_with_cache(
    *,
    method: str,
    url: str,
    params: Optional[Dict[str, Any]],
    headers: Dict[str, str],
    json_body: Any,
    cache: JsonFileCache,
    stats: Dict[str, Any],
    timeout_sec: int = 30,
    min_delay_sec: float = 0.0,
    max_retries: int = 5,
) -> Tuple[int, Dict[str, Any]]:
    """
    先查 cache；沒有才打 API。
    遇到 429 會 backoff 重試。
    回傳：(status_code, json_payload)
    """
    key = stable_request_key(method, url, params, json_body)
    cached = cache.get(key)
    if cached is not None and "data" in cached:
        stats["cache_hits"] += 1
        return int(cached.get("status_code", 200)), cached["data"]

    # 避免太密集（很保守的 throttle）
    if min_delay_sec > 0:
        time.sleep(min_delay_sec)

    stats["api_calls"] += 1
    backoff = 1.0
    last_text = ""
    for attempt in range(max_retries):
        try:
            resp = requests.request(method=method, url=url, params=params, json=json_body, headers=headers, timeout=timeout_sec)
        except Exception as e:
            last_text = repr(e)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue

        status = resp.status_code
        last_text = resp.text[:5000]

        if status == 429:
            # Too Many Requests
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue

        # 有些 endpoint 可能只支援 POST；如果 GET 回 405，就換 POST 再試
        if status == 405 and method.upper() == "GET":
            method = "POST"
            continue

        # 成功或非 429/405 都返回（404/400 由上層處理）
        try:
            data = resp.json()
        except Exception:
            data = {"_raw_text": last_text}

        cache.set(key, {"status_code": status, "data": data})
        return status, data

    # 最後失敗
    cache.set(key, {"status_code": 599, "data": {"_error": last_text}})
    return 599, {"_error": last_text}


# -----------------------------
# Semantic Scholar API wrapper（最小）
# -----------------------------
def s2_headers(api_key: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def s2_get_paper(paper_id: str, *, fields: str, headers: Dict[str, str], cache: JsonFileCache, stats: Dict[str, Any], min_delay_sec: float) -> Tuple[int, Dict[str, Any]]:
    url = f"{S2_BASE}/paper/{paper_id}"
    params = {"fields": fields}
    return request_with_cache(method="GET", url=url, params=params, headers=headers, json_body=None, cache=cache, stats=stats, min_delay_sec=min_delay_sec)


def s2_search_paper(title: str, *, limit: int, fields: str, headers: Dict[str, str], cache: JsonFileCache, stats: Dict[str, Any], min_delay_sec: float) -> Tuple[int, Dict[str, Any]]:
    url = f"{S2_BASE}/paper/search"
    params = {"query": title, "limit": limit, "fields": fields}
    return request_with_cache(method="GET", url=url, params=params, headers=headers, json_body=None, cache=cache, stats=stats, min_delay_sec=min_delay_sec)


def s2_get_references(
    paper_id: str,
    *,
    limit: int,
    fields: str,
    headers: Dict[str, str],
    cache: JsonFileCache,
    stats: Dict[str, Any],
    min_delay_sec: float,
) -> List[Dict[str, Any]]:
    """
    取得 references。為了保持簡單：
    - 先試 offset/limit 的方式（常見）
    - 若回應沒有 pagination 資訊，就直接拿 data
    """
    out: List[Dict[str, Any]] = []
    offset = 0
    # 保守：最多抓 10,000 筆（通常夠用）
    max_total = 10000

    while True:
        url = f"{S2_BASE}/paper/{paper_id}/references"
        params = {"fields": fields, "limit": limit, "offset": offset}
        status, payload = request_with_cache(
            method="GET",
            url=url,
            params=params,
            headers=headers,
            json_body=None,
            cache=cache,
            stats=stats,
            min_delay_sec=min_delay_sec,
        )
        if status != 200:
            # 某些 paper 可能完全沒有 references 或被擋；回空即可
            return out

        data = payload.get("data")
        if not isinstance(data, list):
            return out

        out.extend(data)

        # pagination：如果回來的數量小於 limit，就結束
        if len(data) < limit:
            break

        offset += limit
        if offset >= max_total:
            break

    return out


# -----------------------------
# 讀取輸入：arxiv_metadata.json
# -----------------------------
def load_nodes_from_arxiv_metadata(metadata_json: Path, *, default_label: str) -> List[Node]:
    raw = json.loads(metadata_json.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("arxiv_metadata.json 必須是 JSON array")

    nodes: List[Node] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        md = item.get("metadata") or {}
        if not isinstance(md, dict):
            md = {}
        key = (md.get("key") or "").strip()
        title = (md.get("title") or "").strip()
        if not key:
            # 沒 key 的資料對你沒用；跳過
            continue

        source = (md.get("source") or "").strip()
        source_id = (md.get("source_id") or "").strip()

        arxiv_id = ""
        # 你提供的檔案有兩個地方可能有 arxiv_id
        arxiv_id = extract_arxiv_id_from_any(md.get("arxiv_id")) or ""
        if not arxiv_id:
            arxiv_id = extract_arxiv_id_from_any(item.get("arxiv_id")) or ""

        doi = ""
        if looks_like_doi(source_id):
            doi = normalize_doi(source_id)

        nodes.append(
            Node(
                key=key,
                title=title,
                label=default_label,
                source=source,
                source_id=source_id,
                arxiv_id=arxiv_id,
                doi=doi,
            )
        )

    # key 必須唯一；若重複就保留第一個並 warning
    seen = set()
    uniq: List[Node] = []
    for n in nodes:
        if n.key in seen:
            continue
        seen.add(n.key)
        uniq.append(n)
    return uniq


def load_labels(labels_path: Path) -> Dict[str, str]:
    if not labels_path.exists():
        return {}
    if labels_path.suffix.lower() == ".json":
        obj = json.loads(labels_path.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            return {str(k).strip(): str(v).strip() for k, v in obj.items() if str(k).strip() and str(v).strip()}
        return {}
    # CSV
    out: Dict[str, str] = {}
    with labels_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row.get("key") or "").strip()
            label = (row.get("label") or "").strip()
            if key and label:
                out[key] = label
    return out


# -----------------------------
# Matching：把 S2 ref 映射回你的 node set
# -----------------------------
def build_lookup(nodes: List[Node]) -> Dict[str, Dict[str, str]]:
    """
    回傳多個 lookup dict：
    - by_doi: doi -> key
    - by_arxiv: arxiv_id -> key
    - by_s2_paper_id: s2_paper_id -> key（此時可能還是空，之後可更新）
    - by_norm_title: normalized_title -> key
    """
    by_doi: Dict[str, str] = {}
    by_arxiv: Dict[str, str] = {}
    by_s2: Dict[str, str] = {}
    by_title: Dict[str, str] = {}

    for n in nodes:
        if n.doi:
            by_doi[normalize_doi(n.doi)] = n.key
        if n.arxiv_id:
            by_arxiv[n.arxiv_id] = n.key
        if n.s2_paper_id:
            by_s2[n.s2_paper_id] = n.key
        nt = normalize_title(n.title)
        if nt:
            by_title[nt] = n.key

    return {
        "by_doi": by_doi,
        "by_arxiv": by_arxiv,
        "by_s2": by_s2,
        "by_norm_title": by_title,
    }


def try_match_reference(
    ref: Dict[str, Any],
    lookups: Dict[str, Dict[str, str]],
    *,
    enable_title_fuzzy: bool,
    title_fuzzy_threshold: int,
) -> Optional[Tuple[str, str]]:
    """
    回傳 (dst_key, match_type) 或 None
    """
    by_doi = lookups["by_doi"]
    by_arxiv = lookups["by_arxiv"]
    by_s2 = lookups["by_s2"]
    by_title = lookups["by_norm_title"]

    paper_id = (ref.get("paperId") or "").strip()
    title = (ref.get("title") or "").strip()
    external = ref.get("externalIds") or {}

    # 1) DOI
    doi = ""
    if isinstance(external, dict):
        doi = external.get("DOI") or external.get("doi") or ""
    doi = normalize_doi(str(doi)) if doi else ""
    if doi and doi in by_doi:
        return by_doi[doi], "doi"

    # 2) arXiv
    arxiv = ""
    if isinstance(external, dict):
        arxiv = external.get("ArXiv") or external.get("arXiv") or external.get("arxiv") or ""
    arxiv = extract_arxiv_id_from_any(str(arxiv)) if arxiv else None
    if arxiv and arxiv in by_arxiv:
        return by_arxiv[arxiv], "arxiv"

    # 3) paperId
    if paper_id and paper_id in by_s2:
        return by_s2[paper_id], "paperId"

    # 4) title exact normalize
    nt = normalize_title(title)
    if nt and nt in by_title:
        return by_title[nt], "title_exact"

    # 5) title fuzzy（保守，避免誤配）
    if enable_title_fuzzy and nt and fuzz is not None and by_title:
        best_key = None
        best_score = -1
        for cand_title, cand_key in by_title.items():
            score = fuzz.token_set_ratio(nt, cand_title)  # 0-100
            if score > best_score:
                best_score = score
                best_key = cand_key
        if best_key is not None and best_score >= title_fuzzy_threshold:
            return best_key, "title_fuzzy"

    return None


# -----------------------------
# 主流程：resolve -> references -> edges
# -----------------------------
def resolve_node_to_s2_paper_id(
    node: Node,
    *,
    headers: Dict[str, str],
    cache: JsonFileCache,
    stats: Dict[str, Any],
    min_delay_sec: float,
    enable_title_search: bool,
    title_search_limit: int,
    title_match_threshold: int,
) -> str:
    """
    回傳 resolved S2 paperId（可能為空字串代表失敗）
    """
    # 1) 直接可用的 id（paperId / DOI / arXiv）
    # paper details endpoint 支援：S2PaperId, DOI, ArXivId, URL 等
    direct_id = ""
    if node.source == "semantic_scholar" and node.source_id and not looks_like_doi(node.source_id) and not node.source_id.startswith("http"):
        direct_id = node.source_id
    elif node.doi:
        direct_id = f"DOI:{normalize_doi(node.doi)}"
    elif node.arxiv_id:
        direct_id = f"arXiv:{node.arxiv_id}"

    if direct_id:
        status, payload = s2_get_paper(direct_id, fields="paperId,title,externalIds", headers=headers, cache=cache, stats=stats, min_delay_sec=min_delay_sec)
        if status == 200 and isinstance(payload, dict) and payload.get("paperId"):
            return str(payload["paperId"])

    # 2) title search（最後手段）
    if not enable_title_search:
        return ""

    if not node.title:
        return ""

    status, payload = s2_search_paper(node.title, limit=title_search_limit, fields="paperId,title", headers=headers, cache=cache, stats=stats, min_delay_sec=min_delay_sec)
    if status != 200:
        return ""

    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return ""

    # 用 normalize title +（可選）fuzzy 判斷
    target = normalize_title(node.title)
    best_pid = ""
    best_score = -1

    for cand in data:
        if not isinstance(cand, dict):
            continue
        pid = str(cand.get("paperId") or "").strip()
        t = str(cand.get("title") or "").strip()
        if not pid or not t:
            continue
        cand_nt = normalize_title(t)

        # 先 exact
        if cand_nt == target:
            return pid

        # fuzzy（如果 rapidfuzz 有裝）
        if fuzz is not None:
            score = fuzz.token_set_ratio(target, cand_nt)
        else:
            # 沒 rapidfuzz 就用一個非常保守的替代：只用長度比例
            score = 0

        if score > best_score:
            best_score = score
            best_pid = pid

    if best_score >= title_match_threshold:
        return best_pid
    return ""


def extract_cited_paper_obj(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    references endpoint 常見結構：
      { "citedPaper": { ... } }
    但不同版本可能會變，這裡做保守兼容。
    """
    if "citedPaper" in item and isinstance(item["citedPaper"], dict):
        return item["citedPaper"]
    if "paper" in item and isinstance(item["paper"], dict):
        return item["paper"]
    # fallback：假設 item 本身就像 paper
    return item


def build_edges(
    nodes: List[Node],
    *,
    headers: Dict[str, str],
    cache: JsonFileCache,
    stats: Dict[str, Any],
    min_delay_sec: float,
    enable_title_search: bool,
    title_search_limit: int,
    title_match_threshold: int,
    enable_title_fuzzy: bool,
    title_fuzzy_threshold: int,
    references_page_limit: int,
    logger: logging.Logger,
) -> Tuple[List[Node], List[Edge]]:
    # 先 resolve 每個 node 的 s2 paperId（會更新 node.s2_paper_id）
    for node in tqdm(nodes, desc="Resolve to Semantic Scholar", unit="paper"):
        pid = resolve_node_to_s2_paper_id(
            node,
            headers=headers,
            cache=cache,
            stats=stats,
            min_delay_sec=min_delay_sec,
            enable_title_search=enable_title_search,
            title_search_limit=title_search_limit,
            title_match_threshold=title_match_threshold,
        )
        node.s2_paper_id = pid

    # 更新 lookup（paperId -> key）
    lookups = build_lookup(nodes)
    for node in nodes:
        if node.s2_paper_id:
            lookups["by_s2"][node.s2_paper_id] = node.key

    edges_set: set[Edge] = set()
    edges_by_type: Dict[str, int] = {}

    # 逐個抓 references，建立 edges（只保留 in-list）
    for node in tqdm(nodes, desc="Fetch references & build edges", unit="paper"):
        if not node.s2_paper_id:
            continue

        refs = s2_get_references(
            node.s2_paper_id,
            limit=references_page_limit,
            fields="citedPaper.paperId,citedPaper.title,citedPaper.externalIds",
            headers=headers,
            cache=cache,
            stats=stats,
            min_delay_sec=min_delay_sec,
        )

        for it in refs:
            if not isinstance(it, dict):
                continue
            cited = extract_cited_paper_obj(it)
            if not isinstance(cited, dict):
                continue

            m = try_match_reference(
                cited,
                lookups,
                enable_title_fuzzy=enable_title_fuzzy,
                title_fuzzy_threshold=title_fuzzy_threshold,
            )
            if not m:
                continue
            dst_key, match_type = m
            if dst_key == node.key:
                continue
            e = Edge(src=node.key, dst=dst_key, match_type=match_type)
            if e not in edges_set:
                edges_set.add(e)
                edges_by_type[match_type] = edges_by_type.get(match_type, 0) + 1

    stats["n_edges_by_match_type"] = edges_by_type
    return nodes, sorted(edges_set, key=lambda e: (e.src, e.dst, e.match_type))


# -----------------------------
# 輸出：CSV / GraphML / DOT / HTML
# -----------------------------
def write_nodes_csv(nodes: List[Node], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "title", "label", "source", "source_id", "arxiv_id", "doi", "s2_paper_id"])
        for n in nodes:
            w.writerow([n.key, n.title, n.label, n.source, n.source_id, n.arxiv_id, n.doi, n.s2_paper_id])


def write_edges_csv(edges: List[Edge], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src_key", "dst_key", "match_type"])
        for e in edges:
            w.writerow([e.src, e.dst, e.match_type])


def build_nx_graph(nodes: List[Node], edges: List[Edge]) -> nx.DiGraph:
    g = nx.DiGraph()
    for n in nodes:
        g.add_node(
            n.key,
            title=n.title,
            label=n.label,
            source=n.source,
            source_id=n.source_id,
            arxiv_id=n.arxiv_id,
            doi=n.doi,
            s2_paper_id=n.s2_paper_id,
        )
    for e in edges:
        g.add_edge(e.src, e.dst, match_type=e.match_type)
    return g


def write_graphml(g: nx.DiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(g, path)


def escape_dot(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def write_dot(nodes: List[Node], edges: List[Edge], path: Path, *, color_map: Dict[str, str], show_labels: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("digraph ReferenceGraph {")
    lines.append('  graph [rankdir="TB"];')
    lines.append('  node [shape=circle, style=filled, label=""];')
    lines.append('  edge [color="#888888"];')

    for n in nodes:
        fill = color_map.get(n.label, color_map.get("U", "#95a5a6"))
        label = n.title if show_labels else ""
        tooltip = f"{n.title} ({n.key})"
        lines.append(
            f'  "{escape_dot(n.key)}" [fillcolor="{fill}", label="{escape_dot(label)}", tooltip="{escape_dot(tooltip)}"];'
        )

    for e in edges:
        lines.append(f'  "{escape_dot(e.src)}" -> "{escape_dot(e.dst)}";')

    lines.append("}")
    path.write_text("\n".join(lines), encoding="utf-8")


def compute_hierarchical_levels(nodes: List[Node], edges: List[Edge]) -> Dict[str, int]:
    """
    將有向圖的強連通分量縮成 DAG，依 DAG 拓樸層級給每個 node 分配 level。
    這能避免 cycles 造成 hierarchical layout 全部擠在同一層。
    """
    g = nx.DiGraph()
    g.add_nodes_from(n.key for n in nodes)
    g.add_edges_from((e.src, e.dst) for e in edges)
    if g.number_of_edges() == 0:
        return {n.key: 0 for n in nodes}

    scc = list(nx.strongly_connected_components(g))
    condensed = nx.condensation(g, scc)
    mapping = condensed.graph.get("mapping", {})
    if not mapping:
        mapping = {}
        for idx, comp in enumerate(scc):
            for node in comp:
                mapping[node] = idx

    level: Dict[int, int] = {n: 0 for n in condensed.nodes()}
    for n in nx.topological_sort(condensed):
        preds = list(condensed.predecessors(n))
        if preds:
            level[n] = max(level[p] + 1 for p in preds)

    return {n.key: level.get(mapping.get(n.key, 0), 0) for n in nodes}


def write_html_pyvis(
    nodes: List[Node],
    edges: List[Edge],
    path: Path,
    *,
    color_map: Dict[str, str],
    show_labels: bool,
    hierarchical_direction: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    net = Network(height="900px", width="100%", directed=True, notebook=False)
    levels = compute_hierarchical_levels(nodes, edges)

    # node：預設不顯示文字，只靠顏色
    for n in nodes:
        color = color_map.get(n.label, color_map.get("U", "#95a5a6"))
        label = n.title if show_labels else ""
        title_html = (
            f"<b>{n.title}</b><br/>"
            f"<code>{n.key}</code><br/>"
            + (f"arXiv: {n.arxiv_id}<br/>" if n.arxiv_id else "")
            + (f"DOI: {n.doi}<br/>" if n.doi else "")
            + (f"S2: {n.s2_paper_id}<br/>" if n.s2_paper_id else "")
        )
        node_kwargs: Dict[str, Any] = {
            "label": label,
            "title": title_html,
            "color": color,
            "shape": "dot",
            "size": 8,
        }
        if n.key in levels:
            node_kwargs["level"] = levels[n.key]
        net.add_node(n.key, **node_kwargs)

    for e in edges:
        net.add_edge(e.src, e.dst, arrows="to")

    # hierarchical layout：長得像 DAG
    # 方向：UD = 上到下；LR = 左到右
    force_dir = "vertical" if hierarchical_direction in {"UD", "DU"} else "horizontal"
    options = {
        "layout": {
            "hierarchical": {
                "enabled": True,
                "direction": hierarchical_direction,
                "sortMethod": "directed",
                "nodeSpacing": 180,
                "levelSeparation": 220,
                "treeSpacing": 200,
                "blockShifting": True,
                "edgeMinimization": True,
                "parentCentralization": True,
            },
            "improvedLayout": True,
        },
        "physics": {"enabled": False},
        "interaction": {"hover": True, "navigationButtons": True, "keyboard": True},
        "edges": {"smooth": {"type": "cubicBezier", "forceDirection": force_dir, "roundness": 0.4}},
    }
    net.set_options(json.dumps(options))
    net.write_html(str(path))


# -----------------------------
# 主程式
# -----------------------------
def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build reference citation graph (MVP) from arxiv_metadata.json")
    p.add_argument("--slug", required=True, help="survey slug, e.g. on_the_landscape_of_spoken_language_models_a_comprehensive_survey")
    p.add_argument("--workspace_root", default="", help="default: workspaces/titlepaper_criteria_review (relative to repo root)")
    p.add_argument("--metadata_json", default="", help="override input metadata json path")
    p.add_argument("--out_dir", default="", help="override output dir")
    p.add_argument("--labels", default="", help="labels csv/json path (optional)")
    p.add_argument("--default_label", default="U", help="default label when labels file not provided")
    p.add_argument("--cache_dir", default="", help="default: target_papers/_toolbox/reference_graph/.cache/semantic_scholar")
    p.add_argument("--overwrite", action="store_true", help="overwrite outputs (default behavior)")
    p.add_argument("--show_labels", action="store_true", help="show node text labels (default: hide)")
    p.add_argument("--hier_dir", default="UD", choices=["UD", "DU", "LR", "RL"], help="hierarchical direction in HTML")
    p.add_argument("--min_delay_sec", type=float, default=-1.0, help="min delay between uncached requests; -1=auto")
    p.add_argument("--no_title_search", action="store_false", dest="enable_title_search", default=True,
                   help="disable title search fallback (default: enabled)")
    p.add_argument("--title_search_limit", type=int, default=5, help="S2 search top-K candidates")
    p.add_argument("--title_match_threshold", type=int, default=90, help="title search accept threshold (0-100)")
    p.add_argument("--enable_title_fuzzy", action="store_true", help="enable fuzzy title mapping for references (more edges but risk mis-match)")
    p.add_argument("--title_fuzzy_threshold", type=int, default=95, help="fuzzy match threshold (0-100)")
    p.add_argument("--references_page_limit", type=int, default=1000, help="references endpoint page limit (<=1000 recommended)")
    p.add_argument("--limit", type=int, default=0, help="debug: only process first N nodes (0=all)")
    return p


def main() -> int:
    args = build_argparser().parse_args()

    script_path = Path(__file__).resolve()
    repo_root = find_repo_root(script_path)

    # .env（repo root）
    load_dotenv(repo_root / ".env")

    api_key = os.getenv("S2_API_KEY", "").strip() or os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    headers = s2_headers(api_key)

    ws_root = Path(args.workspace_root) if args.workspace_root else default_workspace_root(repo_root)
    if not ws_root.is_absolute():
        ws_root = (repo_root / ws_root).resolve()

    metadata_json = Path(args.metadata_json) if args.metadata_json else default_metadata_json(ws_root, args.slug)
    if not metadata_json.is_absolute():
        metadata_json = (repo_root / metadata_json).resolve()

    out_dir = Path(args.out_dir) if args.out_dir else default_out_dir(ws_root, args.slug)
    if not out_dir.is_absolute():
        out_dir = (repo_root / out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    log_path = out_dir / "run.log"
    logger = logging.getLogger("reference_graph")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(sh)
    logger.addHandler(fh)

    cache_dir = Path(args.cache_dir) if args.cache_dir else default_cache_dir(repo_root)
    if not cache_dir.is_absolute():
        cache_dir = (repo_root / cache_dir).resolve()
    cache = JsonFileCache(cache_dir)

    stats: Dict[str, Any] = {"api_calls": 0, "cache_hits": 0}

    if not metadata_json.exists():
        logger.error(f"找不到輸入檔：{metadata_json}")
        return 2

    logger.info(f"repo_root = {repo_root}")
    logger.info(f"metadata_json = {metadata_json}")
    logger.info(f"out_dir = {out_dir}")
    logger.info(f"cache_dir = {cache_dir}")
    logger.info(f"api_key = {'YES' if api_key else 'NO'}")

    # auto throttle：有 key 就稍微快一點，沒 key 就保守
    if args.min_delay_sec >= 0:
        min_delay_sec = args.min_delay_sec
    else:
        min_delay_sec = 0.2 if api_key else 1.0

    # 讀 nodes
    nodes = load_nodes_from_arxiv_metadata(metadata_json, default_label=args.default_label)

    # labels 覆蓋（single-label）
    if args.labels:
        labels_path = Path(args.labels)
        if not labels_path.is_absolute():
            labels_path = (repo_root / labels_path).resolve()
        labels = load_labels(labels_path)
        for n in nodes:
            if n.key in labels:
                n.label = labels[n.key]

    if args.limit and args.limit > 0:
        nodes = nodes[: args.limit]

    logger.info(f"n_nodes = {len(nodes)}")

    # edges
    nodes, edges = build_edges(
        nodes,
        headers=headers,
        cache=cache,
        stats=stats,
        min_delay_sec=min_delay_sec,
        enable_title_search=args.enable_title_search,
        title_search_limit=args.title_search_limit,
        title_match_threshold=args.title_match_threshold,
        enable_title_fuzzy=args.enable_title_fuzzy,
        title_fuzzy_threshold=args.title_fuzzy_threshold,
        references_page_limit=args.references_page_limit,
        logger=logger,
    )

    stats["n_nodes"] = len(nodes)
    stats["n_edges"] = len(edges)
    stats["n_papers_resolved"] = sum(1 for n in nodes if n.s2_paper_id)
    stats["n_papers_unresolved"] = sum(1 for n in nodes if not n.s2_paper_id)

    # 顏色（可之後再客製）
    color_map = {
        "A": "#e74c3c",
        "B": "#3498db",
        "C": "#2ecc71",
        "U": "#95a5a6",
    }

    # 輸出
    write_nodes_csv(nodes, out_dir / "nodes.csv")
    write_edges_csv(edges, out_dir / "edges.csv")

    g = build_nx_graph(nodes, edges)
    write_graphml(g, out_dir / "reference_graph.graphml")
    write_dot(nodes, edges, out_dir / "reference_graph.dot", color_map=color_map, show_labels=args.show_labels)
    write_html_pyvis(nodes, edges, out_dir / "reference_graph.html", color_map=color_map, show_labels=args.show_labels, hierarchical_direction=args.hier_dir)

    (out_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Done.")
    logger.info(f"HTML: {out_dir / 'reference_graph.html'}")
    logger.info(f"DOT : {out_dir / 'reference_graph.dot'}")
    logger.info(f"CSV : {out_dir / 'nodes.csv'} / {out_dir / 'edges.csv'}")
    logger.info(f"stats.json: {out_dir / 'stats.json'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
