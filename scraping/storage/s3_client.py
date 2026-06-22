from __future__ import annotations
import gzip
import json
import logging
from datetime import datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from scraping.config import settings

logger = logging.getLogger(__name__)


class S3Store:
    def __init__(self) -> None:
        kwargs: dict = {
            "aws_access_key_id": settings.S3_ACCESS_KEY,
            "aws_secret_access_key": settings.S3_SECRET_KEY,
            "region_name": settings.S3_REGION,
        }
        if settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL

        self._client = boto3.client("s3", **kwargs)
        self._bucket = settings.S3_BUCKET

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                self._client.create_bucket(Bucket=self._bucket)
            else:
                raise

    def save_snapshot(
        self,
        source: str,
        url: str,
        content: str,
        content_type: str = "text/html",
    ) -> Optional[str]:
        try:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_url = url.replace("https://", "").replace("http://", "").replace("/", "_")[:100]
            key = f"snapshots/{source}/{ts}_{safe_url}.html.gz"

            compressed = gzip.compress(content.encode("utf-8", errors="replace"))
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=compressed,
                ContentType=content_type,
                ContentEncoding="gzip",
                Metadata={"source": source, "original_url": url[:512]},
            )
            return key
        except Exception as exc:
            logger.warning("S3 snapshot upload failed for source=%s: %s", source, exc)
            return None

    def save_json_snapshot(self, source: str, data: dict) -> Optional[str]:
        try:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            key = f"snapshots/{source}/{ts}_data.json.gz"
            compressed = gzip.compress(json.dumps(data, default=str).encode())
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=compressed,
                ContentType="application/json",
                ContentEncoding="gzip",
            )
            return key
        except Exception as exc:
            logger.warning("S3 JSON snapshot failed for source=%s: %s", source, exc)
            return None


s3_store = S3Store()
