from typing import Any

from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy

from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages

from ..models import User
from ..forms.claim_forms import VerifyUserCredentialsForm, VerifyUserDOBForm, UpdateUserPasswordForm
from ..services.claim_service import verifyUserCredentials, verifyUserDOB, updateUserPassword

class VerifyCredentialsView(FormView):
    
    template_name = "accounts/claim_account.html"
    form_class = VerifyUserCredentialsForm
    success_url = reverse_lazy("accounts:verify-dob")
    
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
        identifier = form.cleaned_data["identifier"]
        temp_password = form.cleaned_data["temp_password"]        
        
        user = verifyUserCredentials(identifier=identifier, temp_password=temp_password)
        
        if user is not None:
            self.request.session["claim_user_id"] = str(user.id)
            return super().form_valid(form)
        
        messages.error(self.request, "Invalid ID or Password. Please try again")
        
        return self.form_invalid(form)
            
class VerifyUserDOBView(FormView):
    
    template_name = "accounts/claim_account.html"
    form_class = VerifyUserDOBForm
    success_url = reverse_lazy("accounts:update-password")
    
    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["step"] = "verify_date_of_birth"
        context["title"] = "Verify Your Date of Birth"
        
        return context
    
    def form_valid(self, form):
        user_id = self.request.session.get("claim_user_id")
        if not user_id:
            messages.error(self.request, "Session expired, Please restart verification")
            return redirect("accounts:verify-credentials")
        
        user = get_object_or_404(User, id=user_id)
        date_of_birth = form.cleaned_data["date_of_birth"]
        
        user = verifyUserDOB(user=user, date_of_birth=date_of_birth)
        
        if user is not None:
            return super().form_valid(form)
        
        messages.error(self.request, "Date of birth incorrect, Please try again")
        return self.form_invalid(form) 
    
class UpdatePasswordView(FormView):
    
    '''
        This class will get the user id from session
        and first check if that user exist, if so
        allowed them to update their password, and
        redirect to the login screen so that they can 
        login with the new password
    '''
    
    
    template_name = "accounts/claim_account.html"
    form_class = UpdateUserPasswordForm
    success_url = reverse_lazy("accounts:login")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["step"] = "update_password"
        context["title"] = "Update Password"
        
        return context
    
    def form_valid(self, form):
        user_id = self.request.session["claim_user_id"]
        
        if not user_id:
            messages.error(self.request, "Session Expired, Restart Verification")
            return redirect("accounts:verify-credentials")
        
        user = get_object_or_404(User, id=user_id)
        new_password = form.cleaned_data["new_password"]
        
        user = updateUserPassword(user=user, new_password=new_password)
        
        if not user:
            messages.error("Error saving user, Session Expired")
            return redirect("accounts:verify-credentials")
            
        del self.request.session["claim_user_id"]
        
        messages.success(self.request, "Account Claim Successfully, Please login")
        return super().form_valid(form)