"""URL patterns for django-catalog.

Copyright 2025 Nestor Wheelock. All Rights Reserved.
"""
from django.urls import path

from . import views

app_name = 'django_catalog'

urlpatterns = [
    # Dashboard
    path('', views.CatalogDashboardView.as_view(), name='dashboard'),

    # CatalogItem CRUD
    path('items/', views.CatalogItemListView.as_view(), name='catalogitem_list'),
    path('items/add/', views.CatalogItemCreateView.as_view(), name='catalogitem_create'),
    path('items/<int:pk>/', views.CatalogItemDetailView.as_view(), name='catalogitem_detail'),
    path('items/<int:pk>/edit/', views.CatalogItemUpdateView.as_view(), name='catalogitem_edit'),
    path('items/<int:pk>/delete/', views.CatalogItemDeleteView.as_view(), name='catalogitem_delete'),

    # Baskets
    path('baskets/', views.BasketListView.as_view(), name='basket_list'),
    path('baskets/<int:pk>/', views.BasketDetailView.as_view(), name='basket_detail'),

    # WorkItems
    path('workitems/', views.WorkItemListView.as_view(), name='workitem_list'),
    path('workitems/<int:pk>/', views.WorkItemDetailView.as_view(), name='workitem_detail'),
    path('workitems/<int:pk>/edit/', views.WorkItemUpdateView.as_view(), name='workitem_edit'),

    # DispenseLogs
    path('dispense/', views.DispenseLogListView.as_view(), name='dispenselog_list'),
    path('dispense/<int:pk>/', views.DispenseLogDetailView.as_view(), name='dispenselog_detail'),

    # API
    path('api/items/', views.catalog_items_search, name='api_items_search'),
]
