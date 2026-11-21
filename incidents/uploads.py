"""
Media upload view for incident photo and video attachments.
Handles validation and uploads directly to Cloudinary.
"""
import os
import cloudinary
import cloudinary.uploader
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent

# Maximum allowed file size for uploads (50 MB)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Allowed MIME content types
ALLOWED_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'video/mp4',
    'video/quicktime',
}

# Allowed file extensions (lowercase)
ALLOWED_EXTENSIONS = {
    '.jpg',
    '.jpeg',
    '.png',
    '.webp',
    '.mp4',
    '.mov',
}

# Configure Cloudinary credentials explicitly from environment variables
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True,
)


class IncidentMediaUploadView(APIView):
    """
    POST-only endpoint for students to upload photos and videos to Cloudinary.
    """
    permission_classes = [IsStudent]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        # Retrieve uploaded file from multipart form data
        file = request.FILES.get('file')
        if not file and 'file' in request.data:
            candidate = request.data.get('file')
            if hasattr(candidate, 'read'):
                file = candidate

        # 1. Validate file presence
        if not file:
            return Response(
                {"detail": "No file was sent."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Validate file size (50 MB limit)
        if file.size > MAX_UPLOAD_BYTES:
            return Response(
                {"detail": "File is too large (50 MB maximum)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Validate content type and file extension
        _name, ext = os.path.splitext(file.name or '')
        ext = ext.lower()
        content_type = (getattr(file, 'content_type', '') or '').lower()

        if content_type not in ALLOWED_CONTENT_TYPES or ext not in ALLOWED_EXTENSIONS:
            return Response(
                {"detail": "Only photos (JPEG, PNG, WebP) and videos (MP4, MOV) are allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Configure Cloudinary and upload
        cloudinary.config(
            cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
            api_key=os.environ.get('CLOUDINARY_API_KEY'),
            api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
            secure=True,
        )

        try:
            upload_result = cloudinary.uploader.upload(
                file,
                resource_type="auto",
                folder="guardly/incidents",
            )
        except Exception:
            # Catch all exceptions and return a generic 502 error without exposing secrets
            return Response(
                {"detail": "Upload failed. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 5. Determine resource type and return 201 Created
        resource_type = upload_result.get("resource_type")
        if not resource_type:
            resource_type = "video" if content_type.startswith("video/") else "image"

        return Response(
            {
                "url": upload_result.get("secure_url"),
                "resource_type": resource_type,
            },
            status=status.HTTP_201_CREATED,
        )
