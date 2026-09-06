from django.urls import path
from accounts.views.views import *
from .views.claim_views import VerifyCredentialsView, VerifyUserDOBView, UpdatePasswordView

app_name = "accounts"
urlpatterns = [
    path("login/", LogInView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("dashboard/", DashBoardView.as_view(), name="dashboard"),
    
    # Claim-Flow urls
    path("claim/", VerifyCredentialsView.as_view(), name="verify-credentials"),
    path("claim/identity/", VerifyUserDOBView.as_view(), name="verify-dob"),
    path("claim/update_password/", UpdatePasswordView.as_view(), name="update-password")
]