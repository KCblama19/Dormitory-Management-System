from django.db import models

class CampusQuerySet(models.QuerySet):
    """
    Reusable queries for campus operations
    """
    def active(self):
        return self.filter(is_active=True)
    
    def inactive(self):
        return self.filter(is_active=False)
    
    def for_university(self, university):
        university_id = getattr(university, "pk", university)
        
        return self.filter(
            university_id=university_id,
        )
        
    def search(self, term):
        return self.filter(
            models.Q(code__icontains=term)
            | models.Q(name__icontains=term)
            | models.Q(city__icontains=term)
        )
    
    def with_university(self):
        return self.select_related(
            "university",
        )
    