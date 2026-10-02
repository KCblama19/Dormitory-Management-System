from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from django.db.models import Q

# REFERENCE MODELS
from apps.profiles.student.models.student_models import Student
from apps.profiles.staff.models.staff_models import Staff


class MultiIdentifierBackend(ModelBackend):
    """
    Custom authentication backend that allows login using:
    - student_id
    - staff_id
    - email (case insensitive)
    - phone_number

    Fully compatible with Django's authentication system.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Django now uses this method when authenticate is used.
        User = get_user_model()
        
        if not username or not password:
            return None
        
        identifier = username.strip()
        
        # Try to find a matching student
        student=(
            Student.objects
            .with_user()
            .filter(student_id=identifier)
            .first()
        )
        
        if student:
            user = student.user
            
        # Try to find a matching staff
        staff = (
            Staff.objects
            .with_user()
            .filter(staff_id=identifier)
            .first()
        )
        
        if staff:
            user=staff.user
        
        # If the user is admin 
        # Try to authenticate by email/phone
        # if admin id is given we will use it
        # for now to those are okay.     
        if user is None:
            user=(
                user.objects.filter(
                    Q(email__iexact=identifier)
                    | Q(phone_number=identifier)
                ).first()
            )
               
        # user = User.objects.filter(
        #     Q(student_id=identifier)|
        #     Q(staff_id=identifier)|
        #     Q(email__iexact=identifier)|
        #     Q(phone_number=identifier)
        # ).first()
                   
        
        if user is None:
            # # If no user is found, 
            # perform a fake hash to prevent timing attacks
            make_password(password)
            return None    
        
        # Confirm the user password match the one in the database
        # And they are also an active user.
        if ( user.check_password(password) 
            and self.user_can_authenticate(user)
        ):
            return user 
        
        return None