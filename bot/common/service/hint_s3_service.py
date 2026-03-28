"""
S3 для hint viewer: обмен .mat и JSON между ботом и воркерами без Syncthing.
"""
from __future__ import annotations

import os

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from bot.config import settings


class HintS3Storage:
    """Ключи: hints/{game_id}.mat, hints/{game_id}.json, hints/{game_id}_games/..."""

    PREFIX = "hints"

    def __init__(self):
        addressing = settings.S3_ADDRESSING_STYLE.lower().strip()
        if addressing not in ("path", "virtual"):
            addressing = "path"
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_URL.rstrip("/"),
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_ACESS_KEY,
            region_name=settings.S3_REGION,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": addressing},
            ),
        )
        self._bucket = settings.BACKET_NAME

    @classmethod
    def from_settings(cls) -> HintS3Storage:
        return cls()

    @staticmethod
    def mat_key(game_id: str) -> str:
        return f"{HintS3Storage.PREFIX}/{game_id}.mat"

    @staticmethod
    def summary_json_key(game_id: str) -> str:
        return f"{HintS3Storage.PREFIX}/{game_id}.json"

    @staticmethod
    def games_prefix(game_id: str) -> str:
        return f"{HintS3Storage.PREFIX}/{game_id}_games/"

    @staticmethod
    def batch_input_key(batch_id: str, index: int) -> str:
        return f"{HintS3Storage.PREFIX}/batch_in/{batch_id}/{index}.mat"

    @staticmethod
    def game_json_key(game_id: str, game_num: str) -> str:
        return f"{HintS3Storage.PREFIX}/{game_id}_games/game_{game_num}.json"

    def put_source_mat(self, game_id: str, local_path: str) -> str:
        """Загружает локальный .mat в hints/{game_id}.mat, возвращает ключ объекта."""
        key = self.mat_key(game_id)
        self.upload_file(local_path, key)
        return key

    def upload_file(
        self, local_path: str, key: str, content_type: str | None = None
    ) -> None:
        extra = {}
        if content_type:
            extra["ContentType"] = content_type
        kwargs = {}
        if extra:
            kwargs["ExtraArgs"] = extra
        self._client.upload_file(local_path, self._bucket, key, **kwargs)

    def upload_bytes(self, key: str, body: bytes, content_type: str | None = None) -> None:
        kw: dict = {"Bucket": self._bucket, "Key": key, "Body": body}
        if content_type:
            kw["ContentType"] = content_type
        self._client.put_object(**kw)

    def download_file(self, key: str, local_path: str) -> None:
        parent = os.path.dirname(os.path.abspath(local_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._client.download_file(self._bucket, key, local_path)

    def download_bytes(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def upload_tree(self, local_dir: str, s3_prefix: str) -> None:
        base = os.path.abspath(local_dir)
        if not s3_prefix.endswith("/"):
            s3_prefix += "/"
        for root, _, files in os.walk(local_dir):
            for name in files:
                path = os.path.join(root, name)
                rel = os.path.relpath(path, base).replace("\\", "/")
                self.upload_file(path, f"{s3_prefix}{rel}")

    def games_have_any_json(self, game_id: str) -> bool:
        p = self.games_prefix(game_id)
        resp = self._client.list_objects_v2(
            Bucket=self._bucket, Prefix=p, MaxKeys=1
        )
        return bool(resp.get("Contents"))
