from __future__ import annotations

import argparse
import json
import os
import sys

from .config import db_path, ensure_directories
from .db import AgentDB
from .pipeline import MediumAuthorityPipeline
from .review_portal import build_review_portal
from .review_renderer import render_review
from .style_extractor import (
    analyze_text,
    fetch_article_text,
    metrics_as_json,
    write_persona_and_style,
)


def _db() -> AgentDB:
    ensure_directories()
    db = AgentDB(db_path())
    db.init()
    return db


def cmd_init_db(_: argparse.Namespace) -> int:
    db = _db()
    db.init()
    print(f"Initialized DB at {db.path}")
    return 0


def cmd_run_weekly(args: argparse.Namespace) -> int:
    pipeline = MediumAuthorityPipeline(_db())
    results = pipeline.run_weekly(
        count=args.count,
        respect_schedule=args.respect_schedule,
        check_urls=not args.skip_url_check,
    )
    for item in results:
        print(f"{item.status}: {item.article_id or '-'} :: {item.message}")
    return 0


def cmd_run_topic(args: argparse.Namespace) -> int:
    pipeline = MediumAuthorityPipeline(_db())
    result = pipeline.create_from_topic(
        topic=args.topic,
        pillar=args.pillar,
        week_type=args.week_type,
        source_urls=args.source_url or [],
        check_urls=not args.skip_url_check,
    )
    print(f"{result.status}: {result.article_id or '-'} :: {result.message}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    pipeline = MediumAuthorityPipeline(_db())
    path = pipeline.approve(args.id)
    print(f"Approval created: {path}")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    pipeline = MediumAuthorityPipeline(_db())
    dry_run = args.dry_run or os.getenv("AGENT_PUBLISH_DRY_RUN", "false").lower() == "true"
    url, screenshot = pipeline.publish(args.id, dry_run=dry_run)
    print(f"Published: {args.id} -> {url}")
    print(f"Screenshot: {screenshot}")
    return 0


def cmd_publish_approved(args: argparse.Namespace) -> int:
    pipeline = MediumAuthorityPipeline(_db())
    dry_run = args.dry_run or os.getenv("AGENT_PUBLISH_DRY_RUN", "false").lower() == "true"
    published = pipeline.publish_approved(dry_run=dry_run)
    if not published:
        print("No approved items were published.")
        return 0
    print(json.dumps(published, indent=2))
    return 0


def cmd_list_items(args: argparse.Namespace) -> int:
    db = _db()
    rows = db.list_articles(state=args.state)
    print(json.dumps(rows, indent=2))
    return 0


def cmd_extract_style(args: argparse.Namespace) -> int:
    text = fetch_article_text(args.url)
    metrics = analyze_text(text)
    persona_path, style_path = write_persona_and_style(metrics, args.url)
    print(metrics_as_json(metrics))
    print(f"persona: {persona_path}")
    print(f"style: {style_path}")
    return 0


def cmd_render_review(args: argparse.Namespace) -> int:
    db = _db()
    article = db.get_article(args.id)
    metadata = article.get("metadata", {})
    checklist = metadata.get("checklist", {})
    flags = metadata.get("flags", {})
    path = render_review(article, checklist, flags)
    print(f"Review rendered: {path}")
    return 0


def cmd_build_review_hub(_: argparse.Namespace) -> int:
    db = _db()
    index_path, manifest_path = build_review_portal(db)
    print(f"Review hub: {index_path}")
    print(f"Manifest: {manifest_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Medium Authority Engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init-db")
    s.set_defaults(func=cmd_init_db)

    s = sub.add_parser("run-weekly")
    s.add_argument("--count", type=int, default=1)
    s.add_argument("--respect-schedule", action="store_true")
    s.add_argument("--skip-url-check", action="store_true")
    s.set_defaults(func=cmd_run_weekly)

    s = sub.add_parser("run-topic")
    s.add_argument("--topic", required=True)
    s.add_argument("--pillar", default=None)
    s.add_argument("--week-type", default=None)
    s.add_argument("--source-url", action="append", default=[])
    s.add_argument("--skip-url-check", action="store_true")
    s.set_defaults(func=cmd_run_topic)

    s = sub.add_parser("approve")
    s.add_argument("--id", required=True)
    s.set_defaults(func=cmd_approve)

    s = sub.add_parser("publish")
    s.add_argument("--id", required=True)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_publish)

    s = sub.add_parser("publish-approved")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_publish_approved)

    s = sub.add_parser("list-items")
    s.add_argument("--state", default=None)
    s.set_defaults(func=cmd_list_items)

    s = sub.add_parser("extract-style")
    s.add_argument("--url", required=True)
    s.set_defaults(func=cmd_extract_style)

    s = sub.add_parser("render-review")
    s.add_argument("--id", required=True)
    s.set_defaults(func=cmd_render_review)

    s = sub.add_parser("build-review-hub")
    s.set_defaults(func=cmd_build_review_hub)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
