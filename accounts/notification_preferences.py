NOTIFICATION_PREFERENCE_TYPES = (
    "course_announcement",
    "enrollment_confirmation",
    "learning_progress",
    "project_submission",
    "lecturer_feedback",
    "certificate_issued",
    "new_opportunity",
    "application_status",
    "pathway_milestone",
    "platform_announcement",
    "achievement_awarded",
)


def default_notification_preferences():
    return {preference_type: True for preference_type in NOTIFICATION_PREFERENCE_TYPES}
