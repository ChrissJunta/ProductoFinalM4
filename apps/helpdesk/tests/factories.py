"""Archivos de prueba con la firma real de cada tipo."""

from django.core.files.uploadedfile import SimpleUploadedFile

PDF = b"%PDF-1.4\n%prueba\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


def upload(name="comprobante.pdf", content=PDF, content_type="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)
