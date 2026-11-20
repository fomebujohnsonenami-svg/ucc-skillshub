from django.urls import path

from opportunities.views import (
    MyOpportunityApplicationsView,
    OpportunityApplicationDetailView,
    OpportunityApplicationStatusView,
    OpportunityApplyView,
    OpportunityCategoryListView,
    OpportunityDetailView,
    OpportunityListView,
    OpportunityManagerApplicationListView,
    OpportunityManagerDetailView,
    OpportunityManagerListCreateView,
)


urlpatterns = [
    path("opportunities/categories/", OpportunityCategoryListView.as_view(), name="opportunity-categories"),
    path("opportunities/", OpportunityListView.as_view(), name="opportunity-list"),
    path("opportunities/manage/", OpportunityManagerListCreateView.as_view(), name="opportunity-manage-list"),
    path("opportunities/manage/<int:pk>/", OpportunityManagerDetailView.as_view(), name="opportunity-manage-detail"),
    path("opportunities/my-applications/", MyOpportunityApplicationsView.as_view(), name="my-opportunity-applications"),
    path("opportunities/applications/", OpportunityManagerApplicationListView.as_view(), name="opportunity-application-list"),
    path("opportunities/applications/<int:pk>/", OpportunityApplicationDetailView.as_view(), name="opportunity-application-detail"),
    path("opportunities/applications/<int:pk>/status/", OpportunityApplicationStatusView.as_view(), name="opportunity-application-status"),
    path("opportunities/<int:pk>/", OpportunityDetailView.as_view(), name="opportunity-detail"),
    path("opportunities/<int:pk>/apply/", OpportunityApplyView.as_view(), name="opportunity-apply"),
]
