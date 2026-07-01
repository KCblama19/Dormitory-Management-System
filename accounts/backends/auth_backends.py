from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from django.db.models import Q


class MultiIdentifierBackend(ModelBackend):
    """
    Custom authentication backend that allows login using:
    - student_id
    - staff_id
    - email (case insensitive)
    - phone_number

    Fully compatible with Django's authentication system.
    """
    
    def authenticate(self, request, username, password, **kwargs):
        # Django now uses this method when authenticate is used.
        User = get_user_model()
        
        if not username or not password:
            return None
        
        identifier = username.strip()
        
        # Try to find a matching user
        try:
            user = User.objects.filter(
                Q(student_id=identifier)|
                Q(staff_id=identifier)|
                Q(email__iexact=identifier)|
                Q(phone_number=identifier)
            ).first()
                   
            # If no user is found, perform a fake hash to prevent timing attacks
            if user is None:
                make_password(password)
                return None
        # Invalidate the form if multiple users are returned 
        except User.MultipleObjectsReturned:
            return None
        
        if user.check_password(password) and self.user_can_authenticate(user):
            return user 
        
        return None