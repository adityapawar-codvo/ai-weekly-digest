"""Orchestrator for the AI Weekly Digest pipeline. No AI logic of its own — just
wires the stages together per --mode.

  build : collect -> dedupe -> score -> categorize -> summarize -> build email
          -> preview to MAINTAINER_EMAIL only -> persist to data/last_digest.json
  send  : load data/last_digest.json -> send that exact email to config/recipients.yaml
          -> record sent ids to data/sent_history.json
"""

import argparse
import json
import logging
import sys

from agents import categorizer, collector, deduplicator, email_builder, mailer, scorer, summarizer
from core import config, logging_utils

logger = logging.getLogger(__name__)


def run_build() -> None:
    items = collector.collect()
    logging_utils.log_stage("collected", len(items))

    items = deduplicator.dedupe_within_week(items)
    items = deduplicator.dedupe_cross_week(items)
    logging_utils.log_stage("deduped", len(items))

    items = scorer.score_items(items)
    logging_utils.log_stage("scored", len(items))

    items = categorizer.categorize_items(items)
    items = summarizer.summarize_items(items)
    logging_utils.log_stage("summarized", len(items))

    email = email_builder.build_email(items)

    mailer.send(email, [config.MAINTAINER_EMAIL], bcc=False)
    logger.info("Preview sent to maintainer. Review, then run --mode send to approve.")


def run_send() -> None:
    if not config.LAST_DIGEST_PATH.exists():
        raise RuntimeError(
            f"{config.LAST_DIGEST_PATH} not found — run --mode build first to generate a digest."
        )

    with open(config.LAST_DIGEST_PATH, "r") as f:
        digest = json.load(f)

    email = digest["email"]
    item_ids = digest.get("item_ids", [])

    recipients = config.load_recipients()
    mailer.send(email, recipients, bcc=True)

    deduplicator.record_sent(item_ids)
    logging_utils.log_stage("sent", len(recipients))


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Weekly Digest pipeline")
    parser.add_argument("--mode", choices=["build", "send"], required=True)
    args = parser.parse_args()

    logging_utils.setup_logging()

    try:
        if args.mode == "build":
            run_build()
        else:
            run_send()
    except Exception as exc:
        logging_utils.alert_failure(exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
