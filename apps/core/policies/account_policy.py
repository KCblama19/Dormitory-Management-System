from .base import BasePolicy


class AccountPolicy(BasePolicy):
    """
    Authorization rules concerning user accounts and account claiming.
    """

    @classmethod
    def can_claim_own_account(cls, actor):
        """
        A user may participate in claiming their own account.

        The actual verification of identity, temporary password,
        date of birth, and final password belongs to ClaimService.
        """
        return cls.is_authenticated(actor)

    @classmethod
    def can_assist_student_claim(cls, actor, student):
        """
        Global Admin may assist a student with account claiming.

        Assistance does not mean impersonation or unrestricted password
        access. The actual claim workflow remains in ClaimService.
        """
        if not cls.is_global_admin(actor):
            return False

        return student is not None

    @classmethod
    def can_assist_staff_claim(cls, actor, staff):
        """
        Global Admin may assist staff account claiming.
        """
        if not cls.is_global_admin(actor):
            return False

        return staff is not None

    @classmethod
    def can_manage_user_account(cls, actor, user):
        """
        General account administration.

        Global Admin has system-wide account-management authority.
        """
        if not cls.is_global_admin(actor):
            return False

        return user is not None