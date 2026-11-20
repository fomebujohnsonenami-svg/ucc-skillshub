from django.db import migrations


ACHIEVEMENTS = [
    {
        "key": "first-course-completed",
        "name": "First Course Completed",
        "description": "Complete your first eligible course.",
        "badge_image": "/static/certificates/badges/first-course.svg",
        "award_criteria": {"type": "first_course_completed"},
        "category": "course",
    },
    {
        "key": "first-project-approved",
        "name": "First Project Approved",
        "description": "Receive approval for your first practical project.",
        "badge_image": "/static/certificates/badges/first-project.svg",
        "award_criteria": {"type": "project_approved"},
        "category": "project",
    },
    {
        "key": "seven-day-learning-streak",
        "name": "7-Day Learning Streak",
        "description": "Complete learning activities on seven consecutive days.",
        "badge_image": "/static/certificates/badges/learning-streak.svg",
        "award_criteria": {"type": "learning_streak", "days": 7},
        "category": "streak",
    },
    {
        "key": "multiple-courses-completed",
        "name": "Multiple Courses Completed",
        "description": "Complete three courses.",
        "badge_image": "/static/certificates/badges/multiple-courses.svg",
        "award_criteria": {"type": "multiple_courses_completed", "count": 3},
        "category": "course",
    },
    {
        "key": "skill-pathway-completed",
        "name": "Skill Pathway Completed",
        "description": "Complete every step in a skill pathway.",
        "badge_image": "/static/certificates/badges/pathway.svg",
        "award_criteria": {"type": "pathway_completed"},
        "category": "pathway",
    },
    {
        "key": "learning-champion",
        "name": "Learning Champion",
        "description": "Complete ten courses.",
        "badge_image": "/static/certificates/badges/learning-champion.svg",
        "award_criteria": {"type": "learning_champion", "count": 10},
        "category": "community",
    },
]


def create_achievements(apps, schema_editor):
    Achievement = apps.get_model("certificates", "Achievement")
    for data in ACHIEVEMENTS:
        Achievement.objects.get_or_create(key=data["key"], defaults=data)


def remove_achievements(apps, schema_editor):
    Achievement = apps.get_model("certificates", "Achievement")
    Achievement.objects.filter(key__in=[item["key"] for item in ACHIEVEMENTS]).delete()


class Migration(migrations.Migration):
    dependencies = [("certificates", "0001_initial")]

    operations = [migrations.RunPython(create_achievements, remove_achievements)]
