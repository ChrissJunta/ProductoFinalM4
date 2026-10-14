"""Validadores de contraseña propios (ADR-071)."""

from django.core.exceptions import ValidationError


class LettersAndDigitsValidator:
    """Exige al menos una letra y un número."""

    message = "La contraseña debe contener al menos una letra y un número."

    def validate(self, password, user=None):
        if not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)):
            raise ValidationError(self.message, code="password_no_letters_and_digits")

    def get_help_text(self):
        return self.message
