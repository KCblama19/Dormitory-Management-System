from django.db import models

class DepartmentQuerySet(models.QuerySet):
    """
    Reusable queries for department operations
    """
    def active(self):
        return self.filter(is_active=True)
    
    def search(self, term):
        return self.filter(
            models.Q(code__icontains=term)
            | models.Q(name__icontains=term)
        )
            