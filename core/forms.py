from django import forms


class UploadForm(forms.Form):
    CONTENT_CHOICES = [
        ("pdf", "PDF document"),
        ("image", "Image (photo / scan / screenshot)"),
    ]

    content_type = forms.ChoiceField(
        choices=CONTENT_CHOICES,
        widget=forms.RadioSelect,
        initial="pdf",
    )
    file = forms.FileField()

    def clean(self):
        cleaned = super().clean()
        content_type = cleaned.get("content_type")
        f = cleaned.get("file")
        if not f:
            return cleaned

        name = f.name.lower()
        if content_type == "pdf" and not name.endswith(".pdf"):
            raise forms.ValidationError("Please upload a .pdf file, or switch the content type to Image.")
        if content_type == "image" and not name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")):
            raise forms.ValidationError(
                "Please upload an image file (png/jpg/jpeg/webp/bmp/gif), or switch the content type to PDF."
            )
        return cleaned
