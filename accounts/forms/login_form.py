from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError


class LoginForm(forms.Form):
    """
    Logging form that recieve any identifier from 
    the user as the username, the identifier could be 
    a staff_id, student_id, email, or phone number
    and then query if that identifier exist for that user
    if not logging in failed.
    """
    def __init__(self, *args, **kwargs):
        # Get request from form
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
    
    identifier = forms.CharField(required=True)
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_identifier(self):
        identifier = self.cleaned_data.get("identifier")

        if identifier:
            identifier = identifier.strip()

        return identifier

    def clean(self):
        cleaned_data = super().clean()

        identifier = cleaned_data.get("identifier")
        password = cleaned_data.get("password")

        if not identifier or not password:
            return cleaned_data

        # Resolve identifier → user
        # This uses the custom backend I built
        # to authenticate user
        user = authenticate(
            request=self.request,
            username=identifier, 
            password=password)
        
        # Invalid credentials
        if not user:
            raise ValidationError("Invalid credentials")

        # Check activation: This is for staff and student accounts
        # Account exists but not activated
        # if not user.is_claimed:
        #     raise ValidationError(
        #         "Account not activated. Please claim your account."
        #         )
            
        # Attach authenticated user for use in view
        self.user = user

        return cleaned_data
             