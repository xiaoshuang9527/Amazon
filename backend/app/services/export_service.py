"""导出服务：把生成结果导出为 xlsx / json / csv。

- xlsx：贴合亚马逊批量上传（Flat File）的简化结构
- json：贴合 SP-API Listings Items 的 patch 结构
- csv：通用表格
"""

import csv
import io
import os
from typing import Any, Dict, List

from openpyxl import Workbook

from app.core.constants import language_for_marketplace
from app.core.exceptions import AppError

# Flat File 常见列（简化版）
FLAT_FILE_HEADERS = [
    "seller-sku",
    "item-name",
    "product-description",
    "bullet-point1",
    "bullet-point2",
    "bullet-point3",
    "bullet-point4",
    "bullet-point5",
    "generic-keywords",
    "marketplace-id",
    "language",
]


def _pick_sources(results: List[Dict[str, Any]], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """统一 results 结构。"""
    merged: List[Dict[str, Any]] = []
    rows_by_market = {r.get("target_marketplace"): r for r in rows}
    for res in results:
        market = res.get("target_marketplace", "")
        row = rows_by_market.get(market, {})
        merged.append(
            {
                "marketplace": market,
                "language": res.get("target_language")
                or language_for_marketplace(market),
                "sku": row.get("sku") or "",
                "title": res.get("title", ""),
                "bullets": list(res.get("bullets", [])),
                "description": res.get("description", ""),
                "search_terms": res.get("search_terms", ""),
                "suggested_keywords": list(res.get("suggested_keywords", [])),
                "compliance_report": res.get("compliance_report", {}),
            }
        )
    return merged


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def export_json(
    task_id: str, results: List[Dict[str, Any]], rows: List[Dict[str, Any]], out_dir: str
) -> str:
    """导出 SP-API Listings Items patch 结构。"""
    import json

    items = _pick_sources(results, rows)
    patches = []
    for item in items:
        attributes = {
            "item_name": [{"language_tag": item["language"], "value": item["title"]}],
            "product_description": [
                {"language_tag": item["language"], "value": item["description"]}
            ],
            "bullet_point": [
                {"language_tag": item["language"], "value": b} for b in item["bullets"]
            ],
            "generic_keyword": [
                {"language_tag": item["language"], "value": item["search_terms"]}
            ],
        }
        patches.append(
            {
                "sku": item["sku"] or f"TASK-{task_id}",
                "marketplace_id": item["marketplace"],
                "operation_type": "PATCH",
                "product_type": "PRODUCT",
                "patches": [{"op": "replace", "path": "/attributes", "value": attributes}],
                "compliance_report": item["compliance_report"],
            }
        )

    payload = {"task_id": task_id, "version": "2022-07-01", "items": patches}
    path = os.path.join(out_dir, f"listing_{task_id}.json")
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    return path


def export_csv(
    task_id: str, results: List[Dict[str, Any]], rows: List[Dict[str, Any]], out_dir: str
) -> str:
    items = _pick_sources(results, rows)
    path = os.path.join(out_dir, f"listing_{task_id}.csv")
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(FLAT_FILE_HEADERS)
        for item in items:
            bullets = item["bullets"] + [""] * (5 - len(item["bullets"]))
            writer.writerow(
                [
                    item["sku"],
                    item["title"],
                    item["description"],
                    bullets[0],
                    bullets[1],
                    bullets[2],
                    bullets[3],
                    bullets[4],
                    item["search_terms"],
                    item["marketplace"],
                    item["language"],
                ]
            )
    return path


def export_xlsx(
    task_id: str, results: List[Dict[str, Any]], rows: List[Dict[str, Any]], out_dir: str
) -> str:
    items = _pick_sources(results, rows)
    wb = Workbook()
    ws = wb.active
    ws.title = "Listing"
    ws.append(FLAT_FILE_HEADERS)
    for item in items:
        bullets = item["bullets"] + [""] * (5 - len(item["bullets"]))
        ws.append(
            [
                item["sku"],
                item["title"],
                item["description"],
                bullets[0],
                bullets[1],
                bullets[2],
                bullets[3],
                bullets[4],
                item["search_terms"],
                item["marketplace"],
                item["language"],
            ]
        )
    # 追加合规报告 sheet
    ws2 = wb.create_sheet("Compliance")
    ws2.append(["marketplace", "passed", "violations"])
    for item in items:
        report = item["compliance_report"] or {}
        ws2.append(
            [
                item["marketplace"],
                report.get("passed", True),
                "; ".join(v.get("message", "") for v in report.get("violations", [])),
            ]
        )

    path = os.path.join(out_dir, f"listing_{task_id}.xlsx")
    _ensure_dir(path)
    wb.save(path)
    return path


def export(
    fmt: str,
    task_id: str,
    results: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
    out_dir: str,
) -> str:
    fmt = (fmt or "").lower()
    if fmt == "xlsx":
        return export_xlsx(task_id, results, rows, out_dir)
    if fmt == "csv":
        return export_csv(task_id, results, rows, out_dir)
    if fmt == "json":
        return export_json(task_id, results, rows, out_dir)
    raise AppError(f"不支持的导出格式: {fmt}，仅支持 xlsx / json / csv")
