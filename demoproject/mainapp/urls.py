from django.urls import path

from .views import delete_image, edit_image, index


urlpatterns = [
    path('', index, name='index'),
    path('edit/<int:pk>/', edit_image, name='edit_image'),
    path('delete/<int:pk>/', delete_image, name='delete_image'),
]
