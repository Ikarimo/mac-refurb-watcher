#!/usr/bin/env python3
"""Apple認定整備済製品(日本)の在庫を監視し、条件に合う新着をntfyで通知する。

使い方:
  NTFY_TOPIC=<topic> python monitor.py          # 通常実行(新着があれば通知)
  NTFY_TOPIC=<topic> python monitor.py --test   # テスト通知を送る
  python monitor.py                             # 通知なしのドライラン(結果はログのみ)

監視条件は config.json で編集する。
"""
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
GRID_URL = "https://www.apple.com/jp/shop/refurbished/mac"
NTFY_URL = "https://ntfy.sh"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def fetch_html():
    req = urllib.request.Request(
        GRID_URL, headers={"User-Agent": UA, "Accept-Language": "ja-JP,ja"}
    )
    last_err = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(10)
    raise RuntimeError(f"fetch failed after retries: {last_err}")


def extract_tiles(html):
    m = re.search(r"REFURB_GRID_BOOTSTRAP\s*=\s*(\{.*)", html)
    if not m:
        raise RuntimeError("REFURB_GRID_BOOTSTRAP not found (page layout changed?)")
    s = m.group(1)
    depth = 0
    for i, c in enumerate(s):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                s = s[: i + 1]
                break
    return json.loads(s)["tiles"]


def parse_items(tiles):
    items = []
    for t in tiles:
        dims = t.get("filters", {}).get("dimensions", {})
        price_raw = t.get("price", {}).get("currentPrice", {}).get("raw_amount")
        if price_raw is None:
            continue
        mem = int(re.sub(r"\D", "", dims.get("tsMemorySize") or "") or 0)
        part = (
            t.get("omnitureModel", {}).get("partNumber")
            or t.get("price", {}).get("partNumber")
            or ""
        )
        items.append(
            {
                "part": part,
                "model": dims.get("refurbClearModel", ""),
                "title": t.get("title", ""),
                "memory_gb": mem,
                "price": int(float(price_raw)),
                "url": "https://www.apple.com"
                + t.get("productDetailsUrl", "").split("?")[0],
            }
        )
    return items


def matches(item, cfg):
    if item["price"] > cfg.get("max_price", 10**9):
        return False
    for rule in cfg["rules"]:
        if item["model"] != rule["model"]:
            continue
        if rule.get("title_regex") and not re.search(rule["title_regex"], item["title"]):
            continue
        if item["memory_gb"] < rule.get("min_memory_gb", 0):
            continue
        if item["price"] > rule.get("max_price", cfg.get("max_price", 10**9)):
            continue
        return True
    return False


def notify(topic, new_items):
    click = new_items[0]["url"] if len(new_items) == 1 else GRID_URL
    lines = [f"¥{it['price']:,} | {it['title']}" for it in new_items]
    payload = {
        "topic": topic,
        "title": f"Apple整備済に条件一致 {len(new_items)}件!",
        "message": "\n".join(lines)[:3800],
        "click": click,
        "priority": 5,
        "tags": ["rotating_light", "green_apple"],
    }
    req = urllib.request.Request(
        NTFY_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


def main():
    topic = os.environ.get("NTFY_TOPIC")

    if "--test" in sys.argv:
        if not topic:
            sys.exit("NTFY_TOPIC を設定してください")
        notify(
            topic,
            [{"price": 123456, "title": "テスト通知: 監視は正常に動いています", "url": GRID_URL}],
        )
        print(f"test notification sent to {topic}")
        return

    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    state_path = BASE / "state.json"
    prev = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else {"matching": {}}
    )

    items = parse_items(extract_tiles(fetch_html()))
    if not items:
        raise RuntimeError("0 items parsed (page layout changed?)")

    matching = {it["part"]: it for it in items if matches(it, cfg)}
    new_parts = [p for p in matching if p not in prev["matching"]]
    gone = [p for p in prev["matching"] if p not in matching]

    print(
        f"tiles={len(items)} matching={len(matching)} "
        f"new={len(new_parts)} gone={len(gone)}"
    )
    for p in new_parts:
        print(f"NEW: ¥{matching[p]['price']:,} {matching[p]['title']}")

    if new_parts:
        if topic:
            notify(topic, [matching[p] for p in new_parts])
            print("notification sent")
        else:
            print("NTFY_TOPIC not set — notification skipped (dry run)")

    state_path.write_text(
        json.dumps(
            {
                "matching": {
                    p: {"title": v["title"], "price": v["price"]}
                    for p, v in matching.items()
                }
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
