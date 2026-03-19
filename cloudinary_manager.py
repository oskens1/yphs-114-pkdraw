import os
import cloudinary
import cloudinary.uploader
from typing import List
from dotenv import load_dotenv

load_dotenv()

class CloudinaryManager:
    def __init__(self):
        self.cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
        self.api_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
        self.api_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
        
        if self.cloud_name and self.api_key and self.api_secret:
            cloudinary.config(
                cloud_name=self.cloud_name,
                api_key=self.api_key,
                api_secret=self.api_secret,
                secure=True
            )
            print(f"Cloudinary initialized: {self.cloud_name}")
        else:
            print("WARNING: Cloudinary environment variables are missing!")

    def upload_image(self, file_path: str, public_id: str) -> str:
        """上傳本地圖片到 Cloudinary 並返回網址"""
        try:
            response = cloudinary.uploader.upload(
                file_path,
                public_id=public_id,
                folder="pk_draw/works",
                overwrite=True,
                resource_type="image"
            )
            return response.get("secure_url")
        except Exception as e:
            print(f"Cloudinary upload error: {e}")
            return ""

    def upload_images_batch(self, image_paths: List[str]) -> List[str]:
        """批量上傳"""
        urls = []
        for path in image_paths:
            filename = os.path.basename(path).split(".")[0]
            url = self.upload_image(path, filename)
            urls.append(url)
        return urls
