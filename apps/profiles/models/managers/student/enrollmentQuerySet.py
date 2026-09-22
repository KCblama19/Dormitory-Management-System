from django.db import models

class EnrollmentQuerySet(models.QuerySet):
    """
    Reusable queries for Student Enrollment operations
    """
    def active(self):
        return self.filter(
            enrollment_status="ACTIVE",
        )
    
    def completed(self):
        return self.filter(
            enrollment_status="COMPLETED",
        )
    
    def withdrawn(self):
        return self.filter(
            enrollment_status="WITHDRAWN",
        )
    
    def suspended(self):
        return self.filter(
            enrollment_status="SUSPENDED",
        )
        
    def deferred(self):
        return self.filter(
            enrollment_status="DEFERRED",
        )
        
    def primary(self):
        """
        Return the student primary enrollment
        """
        return self.filter(
            is_primary=True,
        )
        
    def primary_active(self):
        """
        Return the current active primary enrollment
        """
        return self.filter(
            self.active().primary(),
        )
        
    def for_student(self, student):
        student_id = getattr(student, "pk", student)
        
        return self.filter(
            student_id=student_id,
        )
        
    def for_academic_year(self, academic_year):
        academic_year_id = getattr(academic_year, "pk", academic_year)
        
        return self.filter(
            academic_year_id=academic_year_id,
        )
        
    def for_program(self, program):
        program_id = getattr(program, "pk", program)
        
        return self.filter(
            program_id=program_id,
        )
        
    
        
    