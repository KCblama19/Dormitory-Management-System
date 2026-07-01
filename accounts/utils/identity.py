import uuid
from datetime import date
from django.contrib.auth import get_user_model


def generate_internal_username(role):
    User = get_user_model()
    """
    source of truth for username generation.

    Used by:
    - UserManager
    - Admin forms
    - Any future services/API
    """

    role_map = {
        User.UserType.STUDENT: "STUDENT",
        User.UserType.STAFF: "STAFF",
        User.UserType.ADMIN: "ADMIN",
    }

    prefix = role_map.get(role, "USER")
    return f"{prefix}_{uuid.uuid4().hex[:10]}"

def get_user_age(date_of_birth):
    today = date.today()
    
    try:
        if date_of_birth.year > today.year:
            return ValueError("Invalid date of birth")
        birthday = date_of_birth.replace(year = today.year)
        
    # raised when birth date is February 29
    # and the current year is not a leap year
    except ValueError:
        birthday = date_of_birth.replace(year = today.year, 
                                         month = date_of_birth.month + 1, 
                                         day = 1)
        
    if birthday > today:
        return today.year - date_of_birth.year - 1
    else:
        return today.year - date_of_birth.year