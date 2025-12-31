"""URL patterns for django-parties.

Copyright 2025 Nestor Wheelock. All Rights Reserved.
"""
from django.urls import path

from . import views

app_name = 'django_parties'

urlpatterns = [
    # Dashboard
    path('', views.PartiesDashboardView.as_view(), name='dashboard'),

    # People CRUD
    path('people/', views.PeopleListView.as_view(), name='people_list'),
    path('people/add/', views.PersonCreateView.as_view(), name='person_create'),
    path('people/<uuid:pk>/', views.PersonDetailView.as_view(), name='person_detail'),
    path('people/<uuid:pk>/edit/', views.PersonUpdateView.as_view(), name='person_edit'),
    path('people/<uuid:pk>/delete/', views.PersonDeleteView.as_view(), name='person_delete'),

    # Organizations CRUD
    path('organizations/', views.OrganizationsListView.as_view(), name='organizations_list'),
    path('organizations/add/', views.OrganizationCreateView.as_view(), name='organization_create'),
    path('organizations/<uuid:pk>/', views.OrganizationDetailView.as_view(), name='organization_detail'),
    path('organizations/<uuid:pk>/edit/', views.OrganizationUpdateView.as_view(), name='organization_edit'),
    path('organizations/<uuid:pk>/delete/', views.OrganizationDeleteView.as_view(), name='organization_delete'),

    # Groups CRUD
    path('groups/', views.GroupsListView.as_view(), name='groups_list'),
    path('groups/add/', views.GroupCreateView.as_view(), name='group_create'),
    path('groups/<uuid:pk>/', views.GroupDetailView.as_view(), name='group_detail'),
    path('groups/<uuid:pk>/edit/', views.GroupUpdateView.as_view(), name='group_edit'),
    path('groups/<uuid:pk>/delete/', views.GroupDeleteView.as_view(), name='group_delete'),

    # Relationships CRUD
    path('relationships/', views.RelationshipsListView.as_view(), name='relationships_list'),
    path('relationships/add/', views.RelationshipCreateView.as_view(), name='relationship_create'),
    path('relationships/<uuid:pk>/edit/', views.RelationshipUpdateView.as_view(), name='relationship_edit'),
    path('relationships/<uuid:pk>/delete/', views.RelationshipDeleteView.as_view(), name='relationship_delete'),
]
