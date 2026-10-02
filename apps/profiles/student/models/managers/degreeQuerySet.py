from django.db import models

class DegreeQuerySet(models.QuerySet):
    """
    Reusable queries for Degree operations
    """
    
    def active(self):
        """
        Return the current active degree
        """
        return self.filter(is_active=True)
    
    def undergraduate(self):
        """
        Return undergraduate degree
        """
        return self.filter(academic_level="UG")
    
    def postgraduate(self):
        """
        Return postgraduate degree
        """
        return self.filter(academic_level=True)
    
    def doctoral(self):
        """
        Return doctoral/PHD degree
        """
        return self.filter(academic_level=True)
    
    def search(self, term):
        return self.filter(
            models.Q(code__icontains=term)
            | models.Q(name__icontains=term)
        )
        
        
    
    