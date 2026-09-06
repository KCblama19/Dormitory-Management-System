from django import forms
from accounts.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from accounts.utils.identity import generate_internal_username, get_user_age

# -------------------
# Custom Admin form
# - This is used to create Users
# - from the admin panel
# - The system does not expose
# - or allow user to register themselves
# - registration or user creation is solely
# - done by admin.
# -------------------


class UserAdminForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "username",
            "role",
            "student_id",
            "staff_id",
            "email",
            "phone_number",
            "is_claimed",
            "date_of_birth",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(
                attrs={"type": "date"}
            )
        }
        
    def clean_email(self):
        email = self.cleaned_data.get("email")
        
        if email:
            try:
                validate_email(email)
            except ValidationError:
                raise forms.ValidationError("Invalid email format")    
        
        return email
    
    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data.get("date_of_birth")
        valid_age = 16
        
        if date_of_birth: 
            age = get_user_age(date_of_birth)
            if age < valid_age:
                raise forms.ValidationError("User needs to 16 and above")
        else:
            raise forms.ValidationError("User date of birth is required")
        
        return date_of_birth
        
        
    def clean(self):
        cleaned_data = super().clean()
        
        role = cleaned_data["role"]
        student_id = cleaned_data.get("student_id")
        staff_id = cleaned_data.get("staff_id")
        email = cleaned_data.get("email")
        date_of_birth = cleaned_data.get("date_of_birth")
        
        if role == User.UserType.STUDENT and not student_id:
            raise forms.ValidationError("Student id is required")
        if role in [User.UserType.STAFF, User.UserType.ADMIN]:
            if not (staff_id or email):
                raise forms.ValidationError("Staff/Admin must have staff_id or email")
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        # -------------------
        # Auto-generate username(based on role)
        # -------------------
        if not user.username:
            if user.role == User.UserType.STUDENT:
                 user.username = generate_internal_username(User.UserType.STUDENT)
            if user.role == User.UserType.STAFF:
                 user.username = generate_internal_username(User.UserType.STAFF)
            if user.role == User.UserType.ADMIN:
                 user.username = generate_internal_username(User.UserType.ADMIN)
        
        user.full_clean()
        
        if commit:
            user.save()
            
        return user 
        