from django import forms
from datetime import date

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

class VerifyUserCredentialsForm(forms.Form):
    student_id = forms.CharField(
        label="Student ID",
        min_length=8,
        max_length=8,
        required=True,
    )

    temp_password = forms.CharField(
        label="Temporary Password",
        widget=forms.PasswordInput,
        min_length=8,
        required=True,
    )

    def clean_student_id(self):
        student_id = self.cleaned_data["student_id"].strip()

        if not student_id.isdigit():
            raise ValidationError(
                "Student ID must contain numbers only."
            )

        return student_id

    def clean_temp_password(self):
        return self.cleaned_data["temp_password"].strip()           
        
    
class VerifyUserIdentityForm(forms.Form):
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Date of Birth",
    )
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        today = date.today()

        # Student must be at least 16 years old.
        if (
            (dob.year + 16, dob.month, dob.day)
            >
            (today.year, today.month, today.day)
        ):
            raise ValidationError(
                "You must be at least 16 years old."
            )

        return dob       
        
    
class UpdateUserPasswordForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput,
        min_length=8,
        required=True,
        label="New Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        min_length=8,
        required=True,
        label="Confirm Password",
    )
    
    def clean_new_password(self):
        new_password = self.cleaned_data["new_password"].strip()
        
        validate_password(new_password)
        
        return new_password
            
    def clean_confirm_password(self):
        return self.cleaned_data["confirm_password"].strip()
        
        
    def clean(self):
        cleaned_data = super().clean()
        
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")
        
        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError(
                    "Password does not match"
                )            
        
        return cleaned_data