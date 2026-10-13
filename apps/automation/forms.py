from django import forms

from .autonomy import MAX_MESSAGE_LENGTH


class AssistantForm(forms.Form):
    message = forms.CharField(
        label="Tu consulta",
        max_length=MAX_MESSAGE_LENGTH,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
