from django.urls import path
from accounts.views import *

app_name = "accounts"

urls_pattern = [
    path("accounts/login", LogInView.as_view(), name="login")
]