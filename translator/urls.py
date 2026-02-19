from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('translate/', views.translator_view, name='translator'),
    path('about/', views.about, name='about'),
    path('history/', views.history, name='history'),
    path('auth/',      views.auth_view,      name='login'),
    path('auth/',      views.auth_view,      name='register'),
    path('logout/',    views.logout_view,    name='logout'),

    # AJAX / API endpoints
    path('api/analyze-frame/', views.analyze_frame, name='analyze_frame'),
    path('api/end-session/', views.end_session, name='end_session'),
    path('api/feedback/', views.submit_feedback, name='submit_feedback'),
]