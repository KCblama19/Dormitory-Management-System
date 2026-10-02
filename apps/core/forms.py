from django import forms


class StyledFormMixin:
    """
    Applies consistent Bootstrap-compatible CSS classes to form fields.

    This keeps presentation concerns out of individual forms while still
    allowing individual forms to customize widgets where necessary.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            widget = field.widget

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")

            elif isinstance(widget, forms.Select):
                existing = widget.attrs.get("class", "")
                widget.attrs["class"] = f"{existing} form-select".strip()

            else:
                existing = widget.attrs.get("class", "")
                widget.attrs["class"] = f"{existing} form-control".strip()


class OperationForm(StyledFormMixin, forms.Form):
    """
    Base form for domain operations.

    Operation forms validate user input only. The corresponding service
    remains responsible for performing the actual business operation.
    """

    pass