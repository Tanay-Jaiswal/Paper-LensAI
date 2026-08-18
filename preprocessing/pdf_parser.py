import fitz  # PyMuPDF
import re

def extract_text_from_pdf(pdf_path_or_bytes):
    """
    Extracts text from a PDF file.
    Args:
        pdf_path_or_bytes: Path to the PDF file or bytes object.
    Returns:
        str: Extracted text.
    """
    text = ""
    try:
        if isinstance(pdf_path_or_bytes, str):
            doc = fitz.open(pdf_path_or_bytes)
        else:
            doc = fitz.open(stream=pdf_path_or_bytes, filetype="pdf")
            
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text("text") + "\n\n"
        doc.close()
        
        # Basic cleanup: remove multiple spaces and newlines
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""
