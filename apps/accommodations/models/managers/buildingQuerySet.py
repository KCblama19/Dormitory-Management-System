from django.db import models

class BuildingQuerySet(models.QuerySet):
    """
    Reusable queries for Building operations
    Building management operations are in the BuildingService
    """
    def with_campus(self):
        return self.select_related(
            "campus",
            "campus__university",
        )
        
    def with_configuration(self):
        return self.select_related(
            "default_bed_configuration",
        )
    
    def with_staff(self):
        return self.prefetch_related(
            "staff_members"
        )
        
    def active(self):
        return self.filter(is_active=True)
    
    def inactive(self):
        return self.filter(is_active=False)
    
    def for_campus(self, campus):
        campus_id = getattr(campus, "pk", campus)
        
        return self.filter(
            campus_id=campus_id,
        )
        
    def international(self):
        return self.filter(
            student_population="INTERNATIONAL",
        )
        
    def chinese(self):
        return self.filter(
            student_population="CHINESE",
        )
        
    def male_only(self):
        return self.filter(
            gender_policy="MALE ONLY",
        )
        
    def female_only(self):
        return self.filter(
            gender_policy="FEMALE ONLY",
        )
    
    def mixed(self):
        return self.filter(
            gender_policy="MIXED",
        )
    
    def search(self, term):
        return self.filter(
            models.Q(building_number__icontains=term)
            | models.Q(name__icontains=term)
            | models.Q(code__icontains=term)
        )
        
    
        
    