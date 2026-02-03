"""
MongoDB Storage Service for PDF files using GridFS.
Replaces Firebase Storage completely.
"""
from pymongo import MongoClient
from gridfs import GridFS
from bson import ObjectId
from typing import Optional
from datetime import datetime
import logging
import ssl

# Try to import certifi for proper SSL certificates
try:
    import certifi

    CERTIFI_AVAILABLE = True
except ImportError:
    CERTIFI_AVAILABLE = False

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class MongoStorageService:
    """Service for storing files in MongoDB using GridFS. Replaces FirebaseService."""

    _instance: Optional['MongoStorageService'] = None
    _client: Optional[MongoClient] = None
    _db = None
    _fs = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        if not settings.mongodb_url:
            logger.warning("MongoDB URL not configured, storage will not work")
            return

        try:
            # Force TLS 1.2 to fix SSL handshake issues
            if CERTIFI_AVAILABLE:
                self._client = MongoClient(
                    settings.mongodb_url,
                    tls=True,
                    tlsCAFile=certifi.where(),
                    tlsAllowInvalidCertificates=False,
                    serverSelectionTimeoutMS=30000,
                    connectTimeoutMS=30000
                )
                logger.info("Using certifi for SSL certificates with TLS")
            else:
                self._client = MongoClient(
                    settings.mongodb_url,
                    tls=True,
                    tlsAllowInvalidCertificates=True,
                    serverSelectionTimeoutMS=30000,
                    connectTimeoutMS=30000
                )
                logger.warning("⚠️ certifi not installed, using insecure SSL connection")

            self._db = self._client.demo_assistant  # Database name
            self._fs = GridFS(self._db)

            # Test connection
            self._client.admin.command('ping')
            logger.info("✅ MongoDB Atlas connected successfully")
            self._initialized = True

        except Exception as e:
            logger.error(f"❌ MongoDB connection error: {e}")
            raise

    async def upload_file(
            self,
            file_data: bytes,
            destination_path: str,
            content_type: str = "application/octet-stream"
    ) -> str:
        """
        Upload file to MongoDB GridFS.
        Compatible interface with FirebaseService.

        Returns: file_id as string (use this to construct download URL)
        """
        try:
            file_id = self._fs.put(
                file_data,
                filename=destination_path,
                content_type=content_type,
                metadata={
                    "uploaded_at": datetime.utcnow(),
                    "original_path": destination_path
                }
            )

            logger.info(f"Uploaded file {destination_path} with ID {file_id}")
            return str(file_id)

        except Exception as e:
            logger.error(f"Failed to upload file {destination_path}: {e}")
            raise

    async def upload_pdf(
            self,
            pdf_data: bytes,
            filename: str,
            user_id: int,
            metadata: dict = None
    ) -> str:
        """
        Upload a PDF file to MongoDB GridFS.

        Args:
            pdf_data: PDF file bytes
            filename: Name of the file
            user_id: Owner user ID
            metadata: Optional additional metadata

        Returns:
            str: File ID (ObjectId as string)
        """
        try:
            file_metadata = {
                "user_id": user_id,
                "filename": filename,
                "content_type": "application/pdf",
                "uploaded_at": datetime.utcnow(),
                **(metadata or {})
            }

            file_id = self._fs.put(
                pdf_data,
                filename=filename,
                content_type="application/pdf",
                metadata=file_metadata
            )

            logger.info(f"Uploaded PDF {filename} with ID {file_id}")
            return str(file_id)

        except Exception as e:
            logger.error(f"Failed to upload PDF {filename}: {e}")
            raise

    async def download_file(self, file_id: str) -> Optional[bytes]:
        """
        Download a file from MongoDB GridFS.

        Args:
            file_id: File ID (ObjectId as string)

        Returns:
            bytes: File content or None if not found
        """
        try:
            object_id = ObjectId(file_id)

            if not self._fs.exists(object_id):
                logger.warning(f"File {file_id} not found")
                return None

            grid_out = self._fs.get(object_id)
            return grid_out.read()

        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            return None

    async def get_file_info(self, file_id: str) -> Optional[dict]:
        """
        Get file metadata without downloading content.

        Args:
            file_id: File ID (ObjectId as string)

        Returns:
            dict: File metadata or None if not found
        """
        try:
            object_id = ObjectId(file_id)

            if not self._fs.exists(object_id):
                return None

            grid_out = self._fs.get(object_id)
            return {
                "id": str(grid_out._id),
                "filename": grid_out.filename,
                "content_type": grid_out.content_type,
                "length": grid_out.length,
                "upload_date": grid_out.upload_date,
                "metadata": grid_out.metadata
            }

        except Exception as e:
            logger.error(f"Failed to get file info {file_id}: {e}")
            return None

    async def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from MongoDB GridFS.

        Args:
            file_id: File ID (ObjectId as string)

        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            object_id = ObjectId(file_id)

            if not self._fs.exists(object_id):
                logger.warning(f"File {file_id} not found for deletion")
                return False

            self._fs.delete(object_id)
            logger.info(f"Deleted file {file_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False

    async def list_user_files(self, user_id: int, prefix: str = "") -> list:
        """
        List all files for a user.

        Args:
            user_id: User ID
            prefix: Optional path prefix filter

        Returns:
            list: List of file metadata dicts
        """
        try:
            files = []
            query = {"metadata.user_id": user_id}

            for grid_out in self._fs.find(query):
                files.append({
                    "id": str(grid_out._id),
                    "filename": grid_out.filename,
                    "content_type": grid_out.content_type,
                    "size": grid_out.length,
                    "created": grid_out.upload_date,
                    "url": f"/api/files/{grid_out._id}"  # API endpoint for download
                })
            return files

        except Exception as e:
            logger.error(f"Failed to list files for user {user_id}: {e}")
            return []

    async def get_signed_url(self, file_id: str, expiration_hours: int = 24) -> str:
        """
        Get download URL for a file.
        MongoDB doesn't need signed URLs - we use our API endpoint.

        Returns: API endpoint URL
        """
        return f"/api/files/{file_id}"

    def close(self):
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed")

    # ==================== CACHE METHODS ====================

    async def save_cached_data(
            self,
            user_id: int,
            project_key: str,
            data: dict,
            date_range_start: datetime = None,
            date_range_end: datetime = None,
            sprint_id: str = None
    ) -> str:
        """
        Save scraped Jira data to cache.
        Replaces existing cache for same user+project.

        Returns: document ID
        """
        try:
            collection = self._db.scraped_data

            # Upsert - replace if exists
            filter_query = {
                "user_id": user_id,
                "jira_project_key": project_key
            }

            document = {
                "user_id": user_id,
                "jira_project_key": project_key,
                "data": data,
                "scraped_at": datetime.utcnow(),
                "date_range_start": date_range_start,
                "date_range_end": date_range_end,
                "sprint_id": sprint_id
            }

            result = collection.replace_one(filter_query, document, upsert=True)

            doc_id = str(result.upserted_id) if result.upserted_id else "updated"
            logger.info(f"Cached data for user {user_id}, project {project_key}")
            return doc_id

        except Exception as e:
            logger.error(f"Failed to cache data: {e}")
            raise

    async def get_cached_data(
            self,
            user_id: int,
            project_key: str,
            max_age_hours: int = 24
    ) -> Optional[dict]:
        """
        Get cached Jira data if exists and not expired.

        Returns: cached data dict or None if not found/expired
        """
        try:
            collection = self._db.scraped_data

            cached = collection.find_one({
                "user_id": user_id,
                "jira_project_key": project_key
            })

            if not cached:
                return None

            # Check age
            scraped_at = cached.get("scraped_at")
            if scraped_at:
                from datetime import timedelta
                age = datetime.utcnow() - scraped_at
                if age > timedelta(hours=max_age_hours):
                    logger.info(f"Cache for {project_key} expired ({age.total_seconds() / 3600:.1f}h old)")
                    return None

            logger.info(f"Using cached data for {project_key}")
            return cached.get("data")

        except Exception as e:
            logger.error(f"Failed to get cached data: {e}")
            return None

    async def get_all_cached_data(self, user_id: int) -> list:
        """Get all cached data for a user."""
        try:
            collection = self._db.scraped_data

            results = []
            for doc in collection.find({"user_id": user_id}):
                results.append({
                    "id": str(doc["_id"]),
                    "project_key": doc.get("jira_project_key"),
                    "scraped_at": doc.get("scraped_at"),
                    "date_range_start": doc.get("date_range_start"),
                    "date_range_end": doc.get("date_range_end"),
                    "issues_count": doc.get("data", {}).get("total_issues", 0)
                })

            return results

        except Exception as e:
            logger.error(f"Failed to get all cached data: {e}")
            return []

    async def delete_cached_data(self, user_id: int, project_key: str = None) -> bool:
        """
        Delete cached data.
        If project_key is None, deletes ALL cache for user.
        """
        try:
            collection = self._db.scraped_data

            if project_key:
                result = collection.delete_one({
                    "user_id": user_id,
                    "jira_project_key": project_key
                })
            else:
                result = collection.delete_many({"user_id": user_id})

            logger.info(f"Deleted {result.deleted_count} cached entries for user {user_id}")
            return result.deleted_count > 0

        except Exception as e:
            logger.error(f"Failed to delete cached data: {e}")
            return False


# Singleton instance getter
def get_mongo_storage() -> MongoStorageService:
    """Get MongoDB storage service instance."""
    return MongoStorageService()