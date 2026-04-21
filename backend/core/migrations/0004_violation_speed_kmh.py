from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_alter_violation_violation_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="violation",
            name="speed_kmh",
            field=models.FloatField(default=0.0, blank=True),
        ),
    ]
