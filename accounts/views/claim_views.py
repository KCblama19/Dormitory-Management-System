from django.shortcuts import redirect

from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages

from ..forms.claim_forms import VerifyUserCredentialsForm, VerifyUserIdentityForm, UpdateUserPasswordForm
from ..services.claim_service import verifyUserCredentials

class VerifyCredentialsView(FormView, LoginRequiredMixin):
    
    template_name = "accounts/claim_account.html"
    form_class = VerifyUserCredentialsForm
    
    def get_context_data(self, **kwargs) -> dict[str,]:
        ''' Send additional information to the view
          I do this because I'm using one template for 
          multiple forms and verification steps
          and the template need more information
          which it will get from context to know
          what form to display, you will see this in the other views 
        '''
        context = super().get_context_data(**kwargs)
        context["step"] = "verify_credentials"
        context["title"] = "Verify your identity"
                
        return context
    
    def form_valid(self, form):
        student_id = form.cleaned_data["student_id"]
        temp_password = form.cleaned_data["temp_password"]        
        
        user = verifyUserCredentials(student_id=student_id, temp_password=temp_password)
        if user is not None:
            return redirect("verify-identity")
        else:
            messages.error(self.request, "Invalid ID or Password. Please try again")
            return self.form_invalid(form)
            
        return super().form_invalid(form)
            
        
    
    
# class VerifyIdentityView():
    
# class UpdatePasswordView():