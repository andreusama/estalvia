from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class RegistroForm(UserCreationForm):
    """Nombre de usuario y contraseña (dos veces), más el código de invitación que da quien comparte la aplicación."""

    codigo = forms.CharField(label="Código de invitación", strip=True)

    class Meta:
        model = get_user_model()
        fields = ("username",)
        labels = {"username": "Nombre de usuario"}
        help_texts = {"username": ""}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Contraseña"
        self.fields["password2"].label = "Repite la contraseña"
        self.fields["password2"].help_text = ""
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "field"
        self.fields["username"].widget.attrs.update(autocomplete="username", autofocus=True)
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"
