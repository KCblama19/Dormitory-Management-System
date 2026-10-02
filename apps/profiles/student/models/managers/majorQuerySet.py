from django.db import models

class MajorQuerySet(models.QuerySet):
    """
    Return reusable queries for Majors
    operations
    """
    def active(self):
        """
        Return the current active major
        """
        return self.filter(is_active=True)
    
    def for_department(self, department):
        """
        Return majors belonging to a department
        """
        department_id = getattr(department, "pk", department)
        
        return self.filter(department_id=department_id)
    
    def search(self, term):
        return self.filter(
            models.Q(code__icontains=term)
            | models.Q(name__icontains=term)
        )     
        