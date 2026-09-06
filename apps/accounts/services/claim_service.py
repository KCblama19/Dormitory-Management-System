from apps.accounts.models import User
from datetime import date
from django.db.models import Q


def verifyUserCredentials(identifier: int, temp_password: str) -> User | None:
    # Check if student exists
    user = User.objects.filter(
        Q(student_id=identifier)|
        Q(staff_id=identifier)).first()
    
    if user:
        # Check if credentials match and 
        # the account has not been claimed
        if user.check_password(temp_password) and user.is_claimed == False:
            return user
        # Return false if credentials match and
        # the account has been claimed
        elif user.check_password(temp_password) and user.is_claimed==True:
            return None
    # Student does not exist        
    else:
        return None # Student don't exist
    
def verifyUserDOB(user: object, date_of_birth: date) -> bool:
    return bool(user and user.date_of_birth == date_of_birth)
        
        
def updateUserPassword(user: object, new_password) -> User:
    if user:
        # Update user password to the new_password
        user.set_password(new_password)
        user.is_claimed = True
        user.save()
        
        return user
    else:
        return None
        