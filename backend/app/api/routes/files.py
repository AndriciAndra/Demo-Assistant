"""
File serving routes for downloading PDFs from MongoDB.
New endpoint to serve files stored in MongoDB GridFS.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from app.services.mongo_storage import get_mongo_storage
from app.api.deps import get_current_user_optional
from app.models import User

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{file_id}")
async def download_file(
        file_id: str,
        current_user: User = Depends(get_current_user_optional)
):
    """
    Download a file from MongoDB.
    Returns the PDF file directly for download.
    """
    try:
        mongo_storage = get_mongo_storage()

        # Get file info first
        file_info = await mongo_storage.get_file_info(file_id)

        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")

        # Download file content
        file_content = await mongo_storage.download_file(file_id)

        if not file_content:
            raise HTTPException(status_code=404, detail="File content not found")

        # Return file as downloadable response
        return Response(
            content=file_content,
            media_type=file_info.get("content_type", "application/pdf"),
            headers={
                "Content-Disposition": f'attachment; filename="{file_info.get("filename", "download.pdf")}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")


@router.get("/{file_id}/view")
async def view_file(
        file_id: str,
        current_user: User = Depends(get_current_user_optional)
):
    """
    View a file inline (opens in browser instead of downloading).
    """
    try:
        mongo_storage = get_mongo_storage()

        file_info = await mongo_storage.get_file_info(file_id)

        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")

        file_content = await mongo_storage.download_file(file_id)

        if not file_content:
            raise HTTPException(status_code=404, detail="File content not found")

        # Return file for inline viewing
        return Response(
            content=file_content,
            media_type=file_info.get("content_type", "application/pdf"),
            headers={
                "Content-Disposition": f'inline; filename="{file_info.get("filename", "document.pdf")}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to view file: {str(e)}")


@router.get("/{file_id}/info")
async def get_file_info(
        file_id: str,
        current_user: User = Depends(get_current_user_optional)
):
    """
    Get file metadata without downloading.
    """
    try:
        mongo_storage = get_mongo_storage()
        file_info = await mongo_storage.get_file_info(file_id)

        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")

        return {
            "id": file_info["id"],
            "filename": file_info["filename"],
            "content_type": file_info["content_type"],
            "size": file_info["length"],
            "upload_date": file_info["upload_date"].isoformat() if file_info.get("upload_date") else None
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get file info: {str(e)}")