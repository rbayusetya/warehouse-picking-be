from __future__ import annotations
import boto3
from botocore.config import Config
from app.config import settings


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
        region_name=settings.s3_region,
    )


def ensure_bucket():
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        client.create_bucket(Bucket=settings.s3_bucket)


def upload_base64_to_s3(base64_data: str, filename: str, content_type: str = "image/png") -> str:
    import base64
    client = get_s3_client()
    ensure_bucket()

    if "," in base64_data:
        base64_data = base64_data.split(",")[1]

    binary_data = base64.b64decode(base64_data)
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=filename,
        Body=binary_data,
        ContentType=content_type,
    )

    url = f"{settings.s3_endpoint}/{settings.s3_bucket}/{filename}"
    return url


def get_presigned_url(key: str, expires: int = 3600) -> str | None:
    client = get_s3_client()
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires,
        )
        return url
    except Exception:
        return None
