from django.db import models

class StudentAssignCampusQuerySet(models.QuerySet):
    """
    Reusable queries for Student assignment
    operations.
    """

    def active(self):
        return self.filter(
            status="ACTIVE",
        )

    def ended(self):
        return self.filter(
            status="ENDED",
        )

    def transferred(self):
        return self.filter(
            status="TRANSFERRED",
        )

    def for_student(self, student):
        student_id = getattr(student, "pk", student)

        return self.filter(
            student_id=student_id,
        )

    def for_campus(self, campus):
        campus_id = getattr(campus, "pk", campus)

        return self.filter(
            campus_id=campus_id,
        )

    def for_academic_year(self, academic_year):
        academic_year_id = getattr(academic_year, "pk", academic_year)

        return self.filter(
            academic_year_id=academic_year_id,
        )

    def current(self):
        """
        Return active campus assignments.

        The service layer remains responsible for deciding whether
        an assignment is allowed to become active.
        """
        return self.active()