import os
import cloudinary
import cloudinary.uploader
from typing import List

class CloudinaryManager:
    def __init__(self):
        self.cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
        self.api_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
        self.api_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
        
        print(f"DEBUG: Initializing Cloudinary with Cloud Name: {self.cloud_name}")
        
        if self.cloud_name and self.api_key and self.api_secret:
            cloudinary.config(
                cloud_name=self.cloud_name,
                api_key=self.api_key,
                api_secret=self.api_secret,
                secure=True
            )
        else:
            print("WARNING: Cloudinary environment variables are missing!")

    def upload_image(self, file_path: str, public_id: str) -> str:
        """上傳本地圖片到 Cloudinary 並返回網址"""
        response = cloudinary.uploader.upload(
            file_path,
            public_id=public_id,
            folder="pk_draw/works"
        )
        return response.get("secure_url")

    def upload_images_batch(self, image_paths: List[str]) -> List[str]:
        """批量上傳（目前簡單循環處理）"""
        urls = []
        for path in image_paths:
            filename = os.path.basename(path).split(".")[0]
            url = self.upload_image(path, filename)
            urls.append(url)
        return urls
