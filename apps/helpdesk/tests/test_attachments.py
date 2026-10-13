import pytest
from django.core.exceptions import ValidationError

from apps.helpdesk.attachments import MAX_ATTACHMENT_BYTES, validate_upload

from .factories import JPG, PDF, PNG, upload


@pytest.mark.parametrize(
    "name,content,expected",
    [
        ("a.pdf", PDF, "application/pdf"),
        ("a.PNG", PNG, "image/png"),
        ("a.jpg", JPG, "image/jpeg"),
        ("a.jpeg", JPG, "image/jpeg"),
    ],
)
def test_valid_files(name, content, expected):
    assert validate_upload(upload(name, content)) == expected


@pytest.mark.parametrize(
    "name,content,code",
    [
        ("script.exe", b"MZ", "type"),
        ("sin_extension", PDF, "type"),
        ("pagina.html", b"<html>", "type"),
        ("vacio.pdf", b"", "empty"),
        ("falso.pdf", PNG, "content"),  # extensión no coincide con el contenido
        ("falso.png", b"<script>alert(1)</script>", "content"),
    ],
)
def test_invalid_files(name, content, code):
    with pytest.raises(ValidationError) as exc:
        validate_upload(upload(name, content))
    assert exc.value.code == code


def test_browser_declared_type_is_ignored():
    # El navegador dice PDF, pero el contenido real es PNG con extensión .png.
    assert validate_upload(upload("a.png", PNG, content_type="application/pdf")) == "image/png"


def test_size_limit():
    validate_upload(upload("max.pdf", PDF + b"0" * (MAX_ATTACHMENT_BYTES - len(PDF))))
    with pytest.raises(ValidationError) as exc:
        validate_upload(upload("grande.pdf", PDF + b"0" * MAX_ATTACHMENT_BYTES))
    assert exc.value.code == "size"


def test_file_pointer_is_rewound():
    f = upload("a.pdf", PDF)
    validate_upload(f)
    assert f.read() == PDF
