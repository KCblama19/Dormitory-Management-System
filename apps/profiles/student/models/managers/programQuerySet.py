from django.db import models

class ProgramQuerySet(models.QuerySet):
    """
    Reusable queries for Programs operations
    """
    def active(self):
        return self.filter(is_active=True)
    
    def degree_programs(self):
        """
        Return all degree programs
        """
        return self.filter(program_type="DEGREE")
    
    def language_programs(self):
        """
        Return all Language programs
        """
        return self.filter(program_type="LANGUAGE")
    
    def exchange_programs(self):
        """
        Return all Exchange programs
        """
        return self.filter(program_type="EXCHANGE")
    
    def visiting_programs(self):
        """
        Return all Visiting programs
        """
        return self.filter(program_type="VISITING")
    
    def short_term_programs(self):
        """
        Return all short term programs
        """
        return self.filter(program_type="SHORT_TERM")
    
    def chinese_taught(self):
        """
        Return all Chinese taught programs
        """
        return self.filter(instruction_language="ZH")
    
    def english_taught(self):
        """
        Return all English taught programs
        """
        return self.filter(instruction_language="EN")
    
    def search(self, term):
        return self.filter(
            models.Q(code__icontains=term)
            | models.Q(name__icontains=term)
        )        
    