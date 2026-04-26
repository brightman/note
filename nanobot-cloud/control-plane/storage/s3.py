import aioboto3
from botocore.exceptions import ClientError

from settings import settings

_session = aioboto3.Session(
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
)


async def get_object(key: str) -> bytes | None:
    async with _session.client("s3", endpoint_url=settings.s3_endpoint) as s3:
        try:
            resp = await s3.get_object(Bucket=settings.s3_bucket, Key=key)
            return await resp["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise


async def put_object(key: str, data: bytes) -> None:
    async with _session.client("s3", endpoint_url=settings.s3_endpoint) as s3:
        await s3.put_object(Bucket=settings.s3_bucket, Key=key, Body=data)


async def delete_object(key: str) -> None:
    async with _session.client("s3", endpoint_url=settings.s3_endpoint) as s3:
        await s3.delete_object(Bucket=settings.s3_bucket, Key=key)


async def ensure_bucket() -> None:
    async with _session.client("s3", endpoint_url=settings.s3_endpoint) as s3:
        try:
            await s3.head_bucket(Bucket=settings.s3_bucket)
        except ClientError:
            await s3.create_bucket(Bucket=settings.s3_bucket)
