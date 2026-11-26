import threading

# PDFium no es thread-safe, ni con documentos distintos: todo uso pasa por aquí.
PDFIUM_LOCK = threading.Lock()
