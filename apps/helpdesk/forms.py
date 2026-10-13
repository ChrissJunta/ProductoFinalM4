from django import forms

from .attachments import validate_upload
from .models import Area, Category, Subcategory, Ticket


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


class MessageForm(forms.Form):
    """Respuesta en la conversación del ticket (CONTRACT-011)."""

    content = forms.CharField(label="Mensaje", max_length=5000, widget=forms.Textarea)
    attachment = forms.FileField(label="Adjunto", required=False)
    request_info = forms.BooleanField(label="Solicitar información al usuario", required=False)

    def clean_attachment(self):
        uploaded = self.cleaned_data.get("attachment")
        if uploaded:
            validate_upload(uploaded)
        return uploaded


class AssignForm(forms.Form):
    """POST de asignación (CONTRACT-012). La autorización la decide `helpdesk.assignment`."""

    version = forms.IntegerField(min_value=1)
    area = forms.IntegerField()
    assignee = forms.IntegerField(required=False)


class MetricsFilterForm(forms.Form):
    """Filtros GET de métricas (CONTRACT-017). Vacío = sin filtro; periodo por defecto 30 días."""

    date_from = forms.DateField(label="Desde", required=False)
    date_to = forms.DateField(label="Hasta", required=False)
    area = forms.ModelChoiceField(label="Área", queryset=Area.objects.all(), required=False)
    category = forms.ModelChoiceField(
        label="Categoría", queryset=Category.objects.all(), required=False
    )
    channel = forms.ChoiceField(
        label="Canal", choices=[("", "Todos")] + Ticket.Channel.choices, required=False
    )

    MAX_DAYS = 366

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("date_from"), cleaned.get("date_to")
        if start and end:
            if start > end:
                self.add_error("date_to", "La fecha final es anterior a la inicial.")
            elif (end - start).days >= self.MAX_DAYS:
                self.add_error("date_to", "El periodo máximo es de un año.")
        return cleaned
