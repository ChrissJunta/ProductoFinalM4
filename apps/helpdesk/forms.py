from django import forms

from .attachments import validate_upload
from .models import Category, Subcategory


class TicketCreateForm(forms.Form):
    """Formulario de FE-003. Solo campos que el usuario decide (SPEC §11)."""

    subject = forms.CharField(label="Asunto", max_length=200)
    description = forms.CharField(label="Descripción", max_length=5000, widget=forms.Textarea)
    category = forms.ModelChoiceField(
        label="Categoría",
        queryset=Category.objects.filter(is_active=True),
        required=False,
    )
    subcategory = forms.ModelChoiceField(
        label="Subcategoría",
        queryset=Subcategory.objects.filter(is_active=True, category__is_active=True),
        required=False,
    )
    attachment = forms.FileField(label="Adjunto", required=False)

    def clean_attachment(self):
        uploaded = self.cleaned_data.get("attachment")
        if uploaded:
            validate_upload(uploaded)
        return uploaded

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get("category")
        subcategory = cleaned.get("subcategory")
        if subcategory and category and subcategory.category_id != category.pk:
            self.add_error("subcategory", "La subcategoría no pertenece a la categoría elegida.")
        return cleaned


def category_tree():
    """Categorías y subcategorías activas, para que el frontend filtre en el cliente."""
    categories = Category.objects.filter(is_active=True).prefetch_related("subcategories")
    return [
        {
            "id": c.pk,
            "name": c.name,
            "subcategories": [
                {"id": s.pk, "name": s.name}
                for s in sorted(c.subcategories.all(), key=lambda s: s.name)
                if s.is_active
            ],
        }
        for c in categories
    ]


class TransitionForm(forms.Form):
    """POST de las acciones de estado (CONTRACT-006)."""

    version = forms.IntegerField(min_value=1)
    reason = forms.CharField(max_length=2000, required=False)
