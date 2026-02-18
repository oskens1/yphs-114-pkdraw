import os
import fitz
import sys

def create_test_pdf(output_path, num_pages=5):
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page()
        # 繪製一些文字
        text = f"Student Work #{i+1}"
        p = fitz.Point(50, 50)
        page.insert_text(p, text, fontsize=40, color=(1, 0, 0) if i%2==0 else (0, 0, 1))
        # 繪製一個矩形
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(50, 100, 500, 700))
        shape.finish(color=(0,0,0), fill=(0.9, 0.9, 0.9))
        shape.commit()
        
    doc.save(output_path)
    doc.close()
    print(f"Test PDF created at {output_path}")

if __name__ == "__main__":
    create_test_pdf("pk_draw/uploads/test_works.pdf")
