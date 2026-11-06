from django.views import View
from django.views.generic import ListView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render

from apps.profiles.student.forms.academic_year_forms import AcademicYearForm
from apps.profiles.student.models.academic_year import AcademicYear
from apps.profiles.student.services.academic_year_service import AcademicYearService

from apps.core.exceptions import DomainError

class AcademicYearListView(LoginRequiredMixin, ListView):
    model = AcademicYear
    template_name = "list_academic_year.html"
    context_object_name = "academic_years"
    ordering = ["-start_date"]

class AcademicYearCreateView(LoginRequiredMixin, View):
          
    def get(self, request):
        
        form = AcademicYearForm()
        
        return render(
            request, 
            "profiles:create_academic_year.html",
            {
                "form": form
            }
        )
    
    def post(self, request):
        
        form = AcademicYearForm(request.POST)
        
        if not form.is_valid():
            return render(
                request, 
                "create_academic_year.html",
                {
                    "form" : form
                }
            )
               
        try:
            AcademicYearService.create(
                actor=request.user,
                **form.cleaned_data
            )

        except DomainError as e:
            messages.error(
                request,
                str(e)
            )
            return render(
                request, 
                "create_academic_year.html",
                {
                    "form" : form
                }
            )
            
        else:
            messages.success(request, "Academic Year created successfully.")
            return redirect(
                "profiles:academic-year-list",
            )
        