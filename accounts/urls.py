from django.urls import path
from accounts.views.views import *

app_name = "accounts"

urlpatterns = [
    path("login", LogInView.as_view(), name="login"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("dashboard", DashBoardView.as_view(), name="dashboard" )
]