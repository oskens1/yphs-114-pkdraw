import os
import fitz  # PyMuPDF
from typing import List
from models import WorkItem

def process_pdf(pdf_path: str, output_dir: str) -> List[WorkItem]:
    """
    將 PDF 拆成單頁圖片，並返回 WorkItem 列表
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    doc = fitz.open(pdf_path)
    work_items = []
    
    for i in range(len(doc)):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 提高解析度
        image_name = f"work_{i+1}.png"
        image_path = os.path.join(output_dir, image_name)
        pix.save(image_path)
        
        # 簡單分配隊伍：單數紅隊，雙數白隊
        team = "red" if (i + 1) % 2 != 0 else "white"
        
        item = WorkItem(
            id=f"W{i+1:03d}",
        image_url=f"/static/uploads/images/{image_name}",
        team=team
        )
        work_items.append(item)
        
    doc.close()
    return work_items
