from django.db import models

class AcademicYearQueryset(models.QuerySet):
    
    def active(self):
        """
        Return academic years currently available for use
        """
        return self.filter(is_active=True)
    
    def current(self):
        """
        Return the current academic year
        """
        return self.filter(is_current=True)
    
    def past(self):
        """
        Return academic years that are not 
        currently active/current
        """
        return self.exclude(is_current=True)
    
    def search(self, term):
        """
        Search academic years by name
        e.g., 2026/2027
        """
        return self.filter(
            name__icontains=term,
        )
    
        
        
        
        