from .base import BasePolicy


class StudentPolicy(BasePolicy):
    """
    Authorization rules for Student records.

    Global Admin:
        system-wide student administration.

    Building Manager:
        manage students within the operational scope of their building.

    Building Staff:
        manage students within their building's operational scope.

    Student:
        may manage/view their own permitted profile information.

    Important:
        Enrollment and campus assignment remain outside this policy's
        administrative authority. Those belong to AcademicPolicy and
        are Admin-only.
    """

    @classmethod
    def can_view_student(cls, actor, student):
        if cls.is_global_admin(actor):
            return True

        if student is None:
            return False

        # Student may view their own student record.
        if cls.is_student_account(actor):
            return (
                getattr(student, "user_id", None)
                == getattr(actor, "pk", None)
            )

        # Current accommodation schema does not yet have a Student →
        # Building/Room/Bed assignment.
        #
        # Therefore we do NOT invent a building-level student scope
        # here. Building-level student administration should be
        # resolved through the future accommodation Assignment model.
        return False

    @classmethod
    def can_update_own_profile(cls, actor, student):
        if not cls.is_student_account(actor):
            return False

        return (
            student is not None
            and getattr(student, "user_id", None)
            == getattr(actor, "pk", None)
        )

    @classmethod
    def can_manage_student(cls, actor, student):
        """
        Administrative student management.

        Admin always has access.

        Manager/Staff require a building relationship to the student.

        That relationship is intentionally not guessed until the
        accommodation Assignment model exists.
        """
        if cls.is_global_admin(actor):
            return True

        if not (
            cls.is_building_manager(actor)
            or cls.is_building_staff(actor)
        ):
            return False

        # Do not infer a building relationship from campus assignment.
        #
        # Campus != Building.
        #
        # The correct relationship will be:
        #
        # Student → Assignment → Room/Bed → Building
        #
        # once Assignment exists.
        return False

    @classmethod
    def can_create_student(cls, actor):
        """
        Student creation is an administrative operation.
        """
        return cls.is_global_admin(actor)

    @classmethod
    def can_accept_student(cls, actor, student):
        return (
            cls.is_global_admin(actor)
            and student is not None
        )

    @classmethod
    def can_reject_student(cls, actor, student):
        return (
            cls.is_global_admin(actor)
            and student is not None
        )

    @classmethod
    def can_withdraw_student(cls, actor, student):
        return (
            cls.is_global_admin(actor)
            and student is not None
        )

    @classmethod
    def can_set_eligibility(cls, actor, student):
        return (
            cls.is_global_admin(actor)
            and student is not None
        )

    @classmethod
    def can_activate_student_account(cls, actor, student):
        return (
            cls.is_global_admin(actor)
            and student is not None
        )

    @classmethod
    def can_deactivate_student_account(cls, actor, student):
        return (
            cls.is_global_admin(actor)
            and student is not None
        )

    @classmethod
    def can_suspend_student_account(cls, actor, student):
        return (
            cls.is_global_admin(actor)
            and student is not None
        )

    @classmethod
    def can_restore_student_account(cls, actor, student):
        return (
            cls.is_global_admin(actor)
            and student is not None
        )