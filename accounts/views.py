from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import FormView, TemplateView, View
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib import messages
from accounts.forms.login_form import LoginForm

class LogInView(FormView):
    """
    Validation and Authentication 
    is already done in the form class(login form)
    """
    template_name="accounts/login.html"
    form_class = LoginForm
    success_url = reverse_lazy("accounts:dashboard")
    
    def dispatch(self, request, *args, **kwargs):
        """
        Prevents authenticated users
        from accessing the login page again
        """
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """
        Inject the request into the form.

        This allows the form to pass request into authenticate(),
        since we are authenticating in the form
        """
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs
    
    def form_valid(self, form):
        user = form.user
               
        login(self.request, user)
        messages.success(self.request, "You are now signed in")
        return super().form_valid(form)
    
class DashBoardView(LoginRequiredMixin, TemplateView):
    template_name="accounts/dashboard.html"
    login_url=reverse_lazy("accounts:login")
    
class LogoutView(FormView):
    def post(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, "You have been sign out")
        return redirect("landing_page") 