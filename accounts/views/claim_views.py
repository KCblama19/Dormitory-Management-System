from django.shortcuts import redirect
from django.shortcuts import get_object_or_404

from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages

from ..models import User

from ..forms.claim_forms import VerifyUserCredentialsForm, VerifyUserIdentityForm, UpdateUserPasswordForm
from ..services.claim_service import verifyUserCredentials, verifyUserIdentity

class VerifyCredentialsView(FormView, LoginRequiredMixin):
    
    template_name = "accounts/claim_account.html"
    form_class = VerifyUserCredentialsForm
    success_url = "accounts:verify-identity"
    
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
        context["title"] = "Verify your credentials"
                
        return context
    
    def form_valid(self, form):
        student_id = form.cleaned_data["student_id"]
        temp_password = form.cleaned_data["temp_password"]        
        
        user = verifyUserCredentials(student_id=student_id, temp_password=temp_password)
        self.request.session["claim_user"] = user.id
        
        if user is not None:
            return redirect("accounts:verify-identity")
        
        messages.error(self.request, "Invalid ID or Password. Please try again")
        
        return self.form_invalid(form)
            
class VerifyIdentityView(FormView, LoginRequiredMixin):
    
    template_name = "accounts/claim_account.html"
    form_class = VerifyUserIdentityForm
    
    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["step"] = "verify_identity"
        context["title"] = "verify your identity"
        
        return context
    
    def form_valid(self, form):
        user_id = self.request.session["claim_user"]
        if not user_id:
            messages.error(self.request, "Session expired, Please restart verification")
            return redirect("accounts:verify-credentials")
        
        user = get_object_or_404(User, id=user_id)
        
        date_of_birth = form.cleaned_data["date_of_birth"]
        
        user = verifyUserIdentity(user=user, date_of_birth=date_of_birth)
        
        if user is not None:
            return redirect("accounts:update-password")
        
        messages.error(self.request, "Date of birth incorrect, Please try again")
        return form.form_invalid(form)
    
    
    
    
# class UpdatePasswordView():