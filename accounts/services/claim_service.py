from ..models import User


def verifyUserCredentials(student_id: int, temp_password: str) -> User | None:
    # Check if student exists
    user = User.objects.get(student_id==student_id)
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
    
def verifyUserIdentity(user: object, date_of_birth: str) -> User | None:
    if user:
        # if DOB matches records.
        if user.date_of_birth == date_of_birth:
            return user
        # if DOB doesn't matches
        else:
            return None
        
def updateUserPassword(user: object, new_password) -> User:
    if user:
        # Update user password to the new_password
        user.set_password(new_password)
        user.is_claimed = True
        user.save()
    # if the user instance doesn't exit
    # return None
    else:
        return None
        