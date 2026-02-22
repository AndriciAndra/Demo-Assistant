"""
Google Drive service for uploading and managing files.
"""
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DriveService:
    """Service for Google Drive file operations."""

    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        self.service = build('drive', 'v3', credentials=credentials)

    async def upload_file(
            self,
            file_data: bytes,
            filename: str,
            mime_type: str,
            folder_id: Optional[str] = None
    ) -> dict:
        """
        Upload a file to Google Drive.

        Args:
            file_data: File content as bytes
            filename: Name for the file in Drive
            mime_type: MIME type of the file
            folder_id: Optional folder ID to upload to (root if None)

        Returns:
            dict with file id, name, and webViewLink
        """
        file_metadata = {
            'name': filename
        }

        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaInMemoryUpload(
            file_data,
            mimetype=mime_type,
            resumable=True
        )

        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()

        logger.info(f"Uploaded file to Drive: {file.get('name')} (ID: {file.get('id')})")

        return {
            'id': file.get('id'),
            'name': file.get('name'),
            'url': file.get('webViewLink')
        }

    async def upload_pdf(
            self,
            pdf_data: bytes,
            filename: str,
            folder_id: Optional[str] = None
    ) -> dict:
        """Upload a PDF file to Google Drive."""
        return await self.upload_file(
            file_data=pdf_data,
            filename=filename,
            mime_type='application/pdf',
            folder_id=folder_id
        )

    async def create_folder(
            self,
            folder_name: str,
            parent_folder_id: Optional[str] = None
    ) -> str:
        """
        Create a folder in Google Drive.

        Returns:
            Folder ID
        """
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]

        folder = self.service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()

        logger.info(f"Created folder in Drive: {folder_name} (ID: {folder.get('id')})")

        return folder.get('id')

    async def get_or_create_app_folder(
            self,
            base_folder_id: Optional[str] = None,
            create_subfolder: bool = False
    ) -> str:
        """
        Get folder ID for uploading files.

        Args:
            base_folder_id: User's configured folder ID
            create_subfolder: If True, create "Demo Assistant" subfolder inside base_folder
                            If False (default), use base_folder directly

        Returns:
            Folder ID to upload files to
        """
        # If user specified a folder and we don't need subfolder, use it directly
        if base_folder_id and not create_subfolder:
            logger.info(f"Using user's configured folder directly: {base_folder_id}")
            return base_folder_id

        # Otherwise, get or create "Demo Assistant" folder
        folder_name = "Demo Assistant"

        # Search for existing folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if base_folder_id:
            query += f" and '{base_folder_id}' in parents"

        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        files = results.get('files', [])

        if files:
            logger.info(f"Found existing Demo Assistant folder: {files[0].get('id')}")
            return files[0].get('id')

        # Create new folder
        return await self.create_folder(folder_name, base_folder_id)

    async def delete_file(self, file_id: str) -> bool:
        """Delete a file from Google Drive."""
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"Deleted file from Drive: {file_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False

    async def get_file_info(self, file_id: str) -> Optional[dict]:
        """Get file metadata from Drive."""
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, webViewLink, mimeType, size'
            ).execute()
            return file
        except Exception as e:
            logger.error(f"Failed to get file info {file_id}: {e}")
            return None