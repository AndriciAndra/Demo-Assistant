import firebase_admin
from firebase_admin import credentials, storage
from typing import Optional
from datetime import timedelta
from app.config import get_settings

settings = get_settings()


class FirebaseService:
    """Service for Firebase blob storage."""
    
    _initialized = False
    
    def __init__(self):
        if not FirebaseService._initialized:
            try:
                cred = credentials.Certificate(settings.firebase_credentials_path)
                firebase_admin.initialize_app(cred, {
                    'storageBucket': settings.firebase_storage_bucket
                })
                FirebaseService._initialized = True
            except Exception as e:
                print(f"Firebase initialization error: {e}")
        
        self.bucket = storage.bucket()
    
    async def upload_file(
        self,
        file_data: bytes,
        destination_path: str,
        content_type: str = "application/octet-stream"
    ) -> str:
        """Upload file to Firebase Storage and return public URL."""
        blob = self.bucket.blob(destination_path)
        blob.upload_from_string(file_data, content_type=content_type)
        
        # Make public and get URL
        blob.make_public()
        return blob.public_url
    
    async def upload_pdf(self, pdf_data: bytes, filename: str, user_id: int) -> str:
        """Upload PDF file."""
        path = f"users/{user_id}/self-reviews/{filename}"
        return await self.upload_file(pdf_data, path, "application/pdf")
    
    async def get_signed_url(
        self,
        file_path: str,
        expiration_hours: int = 24
    ) -> str:
        """Get a signed URL for temporary access."""
        blob = self.bucket.blob(file_path)
        url = blob.generate_signed_url(
            expiration=timedelta(hours=expiration_hours),
            method="GET"
        )
        return url
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file from storage."""
        try:
            blob = self.bucket.blob(file_path)
            blob.delete()
            return True
        except Exception:
            return False
    
    async def list_user_files(self, user_id: int, prefix: str = "") -> list:
        """List all files for a user."""
        path = f"users/{user_id}/{prefix}"
        blobs = self.bucket.list_blobs(prefix=path)
        return [
            {
                "name": blob.name,
                "size": blob.size,
                "created": blob.time_created,
                "url": blob.public_url
            }
            for blob in blobs
        ]
