import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from typing import Optional

from app.core.config import settings

class StorageServiceException(Exception):
    pass

class StorageService:
    """Provides reliable storage via MinIO/S3."""
    
    _client = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            # Construct endpoint URL
            protocol = "https" if settings.MINIO_SECURE else "http"
            # Remove protocol from endpoint if it's there
            endpoint = settings.MINIO_ENDPOINT.replace("http://", "").replace("https://", "")
            
            cls._client = boto3.client(
                's3',
                endpoint_url=f"{protocol}://{endpoint}",
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                config=Config(signature_version='s3v4'),
                region_name='us-east-1' # Default for MinIO
            )
        return cls._client

    @classmethod
    def ensure_bucket(cls) -> None:
        """Create bucket if it does not exist."""
        client = cls.get_client()
        bucket = settings.MINIO_BUCKET
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                try:
                    client.create_bucket(Bucket=bucket)
                except Exception as create_e:
                    raise StorageServiceException(f"Failed to create bucket '{bucket}': {str(create_e)}")
            else:
                raise StorageServiceException(f"Error checking bucket '{bucket}': {str(e)}")

    @classmethod
    def upload_file(cls, file_path: str, object_name: str) -> str:
        """Upload a local file to MinIO and return the object key."""
        cls.ensure_bucket()
        client = cls.get_client()
        try:
            client.upload_file(file_path, settings.MINIO_BUCKET, object_name)
            return object_name
        except Exception as e:
            raise StorageServiceException(f"Failed to upload {file_path} to {object_name}: {str(e)}")

    @classmethod
    def download_file(cls, object_name: str, download_path: str) -> str:
        """Download an object from MinIO to a local path."""
        client = cls.get_client()
        try:
            os.makedirs(os.path.dirname(download_path), exist_ok=True)
            client.download_file(settings.MINIO_BUCKET, object_name, download_path)
            return download_path
        except Exception as e:
            raise StorageServiceException(f"Failed to download {object_name} to {download_path}: {str(e)}")

    @classmethod
    def exists(cls, object_name: str) -> bool:
        """Check if an object exists in MinIO."""
        client = cls.get_client()
        try:
            client.head_object(Bucket=settings.MINIO_BUCKET, Key=object_name)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            raise StorageServiceException(f"Error checking if {object_name} exists: {str(e)}")

    @classmethod
    def delete_file(cls, object_name: str) -> None:
        """Delete an object from MinIO."""
        client = cls.get_client()
        try:
            client.delete_object(Bucket=settings.MINIO_BUCKET, Key=object_name)
        except Exception as e:
            raise StorageServiceException(f"Failed to delete {object_name}: {str(e)}")
