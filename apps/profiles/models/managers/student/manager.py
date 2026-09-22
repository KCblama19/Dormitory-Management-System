from django.db import models

class StudentQueryset(models.QuerySet):
    """
    Queryset methods for student
    
    These methods represents reusable database
    queries that can be use for a student
    
    Business operations such as changing
    eligibility, suspending a student, or assigning a
    student, etc to a campus have been placed in the 
    services 
    """
    def with_related(self):
        """
        Return the User connected to this student profile
        and their assignCampus information
        """
        return self.select_related("user", "")
        
    
    def active(self):
        """
        Return students whose user accounts are
        active.
        
        This does not mean the student is 
        academically active or housing eligible.
        It only checks the associated user account status
        """
        return self.filter(user__accountStatus="ACTIVE")
    
    def admitted(self):
        """
        Return students who have been accepted
        by the university
        """
        return self.filter(admission_status="ACCEPTED")
    
    def eligible(self):
        """
        Return students currently marked as eligible
        for accommodation
        """
        return self.filter(eligibility_status="ELIGIBLE")
    
    def ineligible(self):
        """
        Return students currently marked as 
        ineligible for accommodation
        """
        return self.filter(eligibility_status="INELIGIBLE")
    
    def pending_eligibility(self):
        """
        Return students whose accommodation eligibility
        has not been determined 
        """
        return self.filter(eligibility_status="PENDING")
    
    def suspended(self):
        """
        Return students whose accommodation eligibility
        has been suspended
        """
        return self.filter(eligibility_status="SUSPENDED")
    
    def with_active_enrollment(self):
        """
        Return students with at least one active 
        enrollment
        
        Distinct is used because a student can have
        multiple enrollment records that may otherwise 
        produce duplicate rows
        """
        return self.filter(
            enrollment__enrollment_status="ACTIVE"
        ).distinct()
        
    def with_active_campus(self):
        """
        Return students with an active campus 
        assignment
        """
        return self.filter(
            campus_assignment__status="ACTIVE"
        )
        
    def ready_for_accommodation(self):
        """
        Return students satisfying the basic pre-booking
        conditions
        
        This is NOT a complete booking authorization
        check. Booking-period rules and booking rules
        belong are in the booking service.
        
        Current foundation/basic requirement
        
        - active user account
        - accepted admission
        - eligible for accommodation
        - active enrollment
        - active campus assignment
        """
        return (
            self.active()
            .admitted()
            .eligible()
            .with_active_enrollment()
            .with_active_campus
        )
        
    def for_campus(self, campus):
        """
        Return students currently assigned to the
        specified campus
        """
        campus_id = getattr(campus, "pk", campus)
        
        return self.filter(
            campus_assignments__campus_id=campus_id,
            campus_assignment_status="ACTIVE",
        ).distinct()
        
    def for_academic_year(self, academic_year):
        """
        Return students with an active campus assignment
        for the specified academic year.
        """
        academic_year_id = getattr(academic_year, "pk", academic_year)
        
        return self.filter(
            campus_assignment_academic_year_id=academic_year_id,
            campus_assignment__status="ACTIVE",
        )
        
    def search(self, term):
        """
        Search students by common identifying information
        
        This method is intended for administrative
        interfaces and autocomplete/search functionality
        """
        return self.filter(
            models.Q(student_id__icontains=term)
            | models.Q(first_name__icontains=term)
            | models.Q(last_name__icontains=term)
            | models.Q(user__username__icontains=term)
            | models.Q(user__email__icontains=term)
        ).distinct()
        
        
        
        
        
        
        
        
        
        
        
        
        
        
    