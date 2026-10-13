"""Validación de adjuntos (SPEC §26 `Attachment`, §48).

El tipo se decide por la firma del contenido (magic bytes), no por lo que
declara el navegador, y debe coincidir con la extensión.
"""

from django.core.exceptions import ValidationError

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024  # 5 MB

# extensión → (tipo MIME, firma inicial del archivo)
ALLOWED_TYPES = {
    "pdf": ("application/pdf", b"%PDF-"),
    "png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    "jpg": ("image/jpeg", b"\xff\xd8\xff"),
    "jpeg": ("image/jpeg", b"\xff\xd8\xff"),
}


def validate_upload(uploaded_file):
    """Valida extensión, tamaño y contenido. Devuelve el tipo MIME real."""
    name = uploaded_file.name or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_TYPES:
        raise ValidationError("Tipo de archivo no permitido. Use PDF, PNG o JPG.", code="type")
    if uploaded_file.size == 0:
        raise ValidationError("El archivo está vacío.", code="empty")
    if uploaded_file.size > MAX_ATTACHMENT_BYTES:
        raise ValidationError("El archivo supera el tamaño máximo de 5 MB.", code="size")

    content_type, signature = ALLOWED_TYPES[ext]
    uploaded_file.seek(0)
    head = uploaded_file.read(len(signature))
    uploaded_file.seek(0)
    if head != signature:
        raise ValidationError(
            "El contenido del archivo no corresponde a su extensión.", code="content"
        )
    return content_type
