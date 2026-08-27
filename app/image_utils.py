import os
import io
import uuid
import base64
import shutil
from PIL import Image, ImageOps
from fastapi import UploadFile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

def process_and_encode_image(
    upload_file: UploadFile, 
    subfolder: str = "users", 
    max_size: tuple = (300, 300), 
    quality: int = 85
) -> str:
    """
    Processes an uploaded profile / voter image:
    1. Reads image and applies EXIF orientation transpose.
    2. Resizes & optimizes to compact dimensions (default 300x300).
    3. Saves a local copy to static/uploads/{subfolder}/.
    4. Encodes to an optimized base64 Data URI ('data:image/jpeg;base64,...').
    
    Storing the base64 Data URI directly in the database makes user profile photos
    and voter photos 100% permanent and resilient across git pushes, server redeploys,
    and ephemeral cloud environments!
    """
    if not upload_file or not upload_file.filename:
        return None

    upload_dir = os.path.join(STATIC_DIR, "uploads", subfolder)
    os.makedirs(upload_dir, exist_ok=True)

    try:
        content = upload_file.file.read()
        if not content:
            return None

        # Open image with Pillow
        image = Image.open(io.BytesIO(content))
        
        # Handle EXIF orientation
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass

        # Convert RGBA/P to RGB for clean JPEG compression
        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(image, mask=image.split()[-1] if "A" in image.mode else None)
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        # Resize maintaining aspect ratio
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Save to JPEG buffer
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=quality, optimize=True)
        img_bytes = buf.getvalue()

        # Save physical file to disk as well
        prefix = subfolder[:-1] if subfolder.endswith("s") else subfolder
        filename = f"{prefix}_{uuid.uuid4().hex[:12]}.jpg"
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            f.write(img_bytes)

        # Generate Base64 Data URI
        b64_str = base64.b64encode(img_bytes).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{b64_str}"
        return data_uri

    except Exception as e:
        print(f"Image processing note: {e}")
        # Fallback to direct file save if Pillow processing fails
        try:
            upload_file.file.seek(0)
            ext = os.path.splitext(upload_file.filename)[1].lower() or ".jpg"
            filename = f"fallback_{uuid.uuid4().hex[:12]}{ext}"
            file_path = os.path.join(upload_dir, filename)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(upload_file.file, f)
            return f"/static/uploads/{subfolder}/{filename}"
        except Exception:
            return None
