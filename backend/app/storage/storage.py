from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
import os
from pathlib import Path
import shutil
import uuid
from datetime import datetime


class StorageBackend(ABC):
    """Abstract base class for storage backends"""
    
    @abstractmethod
    async def save(self, file: BinaryIO, filename: str, folder: str = "") -> str:
        """Save a file and return its path/key"""
        pass
    
    @abstractmethod
    async def delete(self, file_path: str) -> bool:
        """Delete a file"""
        pass
    
    @abstractmethod
    async def get_url(self, file_path: str) -> str:
        """Get the URL to access the file"""
        pass
    
    @abstractmethod
    def exists(self, file_path: str) -> bool:
        """Check if file exists"""
        pass

    @abstractmethod
    def move(self, src: str, dst: str) -> bool:
        """Move a file from src path to dst path within the same storage"""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage implementation"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    async def save(self, file: BinaryIO, filename: str, folder: str = "") -> str:
        """Save file to local filesystem"""
        # Create unique filename to avoid collisions
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        name, ext = os.path.splitext(filename)
        safe_filename = f"{timestamp}_{unique_id}_{name}{ext}"
        
        # Create folder structure
        folder_path = self.base_path / folder if folder else self.base_path
        folder_path.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = folder_path / safe_filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file, buffer)
        
        # Return relative path from base
        return str(Path(folder) / safe_filename) if folder else safe_filename
    
    async def delete(self, file_path: str) -> bool:
        """Delete file from local filesystem"""
        try:
            full_path = self.base_path / file_path
            if full_path.exists():
                full_path.unlink()
                return True
            return False
        except Exception:
            return False
    
    async def get_url(self, file_path: str) -> str:
        """Get URL for local file (API endpoint)"""
        return f"/api/v1/files/{file_path}"
    
    def exists(self, file_path: str) -> bool:
        """Check if file exists locally"""
        return (self.base_path / file_path).exists()
    
    def get_full_path(self, file_path: str) -> Path:
        """Get full filesystem path"""
        return self.base_path / file_path

    def move(self, src: str, dst: str) -> bool:
        """Move a file within local storage."""
        try:
            src_path = self.base_path / src
            dst_path = self.base_path / dst
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))
            return True
        except Exception:
            return False


class S3StorageBackend(StorageBackend):
    """AWS S3 storage implementation"""
    
    def __init__(self, bucket_name: str, region: str, access_key: str, secret_key: str, endpoint_url: str = None):
        self.bucket_name = bucket_name
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint_url = endpoint_url
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of S3 client"""
        if self._client is None:
            import boto3
            client_kwargs = {
                'service_name': 's3',
                'region_name': self.region,
                'aws_access_key_id': self.access_key,
                'aws_secret_access_key': self.secret_key
            }
            if self.endpoint_url:
                client_kwargs['endpoint_url'] = self.endpoint_url
            self._client = boto3.client(**client_kwargs)
        return self._client
    
    async def save(self, file: BinaryIO, filename: str, folder: str = "") -> str:
        """Upload file to S3"""
        # Create unique key
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        name, ext = os.path.splitext(filename)
        safe_filename = f"{timestamp}_{unique_id}_{name}{ext}"
        
        # Build S3 key
        key = f"{folder}/{safe_filename}" if folder else safe_filename
        
        # Upload to S3
        self.client.upload_fileobj(file, self.bucket_name, key)
        
        return key
    
    async def delete(self, file_path: str) -> bool:
        """Delete file from S3"""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except Exception:
            return False
    
    async def get_url(self, file_path: str) -> str:
        """Generate presigned URL for S3 object"""
        url = self.client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket_name, 'Key': file_path},
            ExpiresIn=3600  # 1 hour
        )
        return url
    
    def exists(self, file_path: str) -> bool:
        """Check if file exists in S3"""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except Exception:
            return False

    def move(self, src: str, dst: str) -> bool:
        """Move a file within S3 by copying then deleting the source."""
        try:
            self.client.copy_object(
                Bucket=self.bucket_name,
                CopySource={'Bucket': self.bucket_name, 'Key': src},
                Key=dst,
            )
            self.client.delete_object(Bucket=self.bucket_name, Key=src)
            return True
        except Exception:
            return False


def get_storage_backend() -> StorageBackend:
    """Factory function to get the configured storage backend"""
    from app.core.config import settings
    
    if settings.STORAGE_BACKEND == "s3":
        return S3StorageBackend(
            bucket_name=settings.S3_BUCKET_NAME,
            region=settings.S3_REGION,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            endpoint_url=settings.S3_ENDPOINT_URL if settings.S3_ENDPOINT_URL else None
        )
    else:
        return LocalStorageBackend(settings.LOCAL_STORAGE_PATH)


# Global storage instance
storage = get_storage_backend()
