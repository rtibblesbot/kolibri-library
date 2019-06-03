"""
Thumbnails from PDFs

Sample code for how to generate thumbnails from PDFs
"""

import requests
import tempfile
from pdf2image import convert_from_path
from PIL import Image
from smartcrop import scale_and_crop
import subprocess

# 1. Thumbails for book
# Use crop="smart" to extract the most "interesting" part of the book cover (assume it's the first page of the PDF)

def pdf_smart_crop(book_path, thumbnail_path, chapter=False, selected_page=0):
    RESOLUTION = 100  # dpi
    pages = convert_from_path(book_path, dpi=RESOLUTION, first_page=1, last_page=1)
    page = pages[selected_page]
    if chapter:
        # crop just the top part
        ASPECT_RATIO = 16.0/9.0             # Kolibri thumbnails are 16:9
        pagewidth, pageheight = page.size   # Get page dimensions
        desired_height = int(pagewidth/ASPECT_RATIO)
        page = page.crop( (0, 0, pagewidth, desired_height))
        zoom = 10
    else:
        zoom = None
    CONTENT_THUMB_SIZE = (160, 90) #(160, 90)# 420, 236
    book_thumb = scale_and_crop(page, CONTENT_THUMB_SIZE, crop="smart", zoom=zoom)
    book_thumb.save(thumbnail_path)

if __name__ == "__main__":
    sample_book_path = "sample/sample_book.pdf"
    sample_chapter_path = "sample/sample_chapter.pdf"
    book_thumbnail_path = "book_thumb.png"
    chapter_thumbnail_path = "chapter_thumb.png"

    pdf_smart_crop(sample_book_path, book_thumbnail_path)
    pdf_smart_crop(sample_chapter_path, chapter_thumbnail_path, chapter=True)

    subprocess.check_output(["gimp", book_thumbnail_path, chapter_thumbnail_path])
