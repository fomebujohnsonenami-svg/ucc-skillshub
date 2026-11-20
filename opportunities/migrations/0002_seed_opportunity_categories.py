from django.db import migrations


CATEGORIES = (
    ("Internships", "internships", 1),
    ("Campus Jobs", "campus-jobs", 2),
    ("Freelance Opportunities", "freelance-opportunities", 3),
    ("Graduate Jobs", "graduate-jobs", 4),
    ("Competitions", "competitions", 5),
)


def create_categories(apps, schema_editor):
    category_model = apps.get_model("opportunities", "OpportunityCategory")
    for name, slug, sort_order in CATEGORIES:
        category_model.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "sort_order": sort_order,
                "is_active": True,
            },
        )


def remove_categories(apps, schema_editor):
    category_model = apps.get_model("opportunities", "OpportunityCategory")
    category_model.objects.filter(
        slug__in=[slug for _, slug, _ in CATEGORIES],
        opportunities__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("opportunities", "0001_initial")]

    operations = [
        migrations.RunPython(create_categories, remove_categories),
    ]
