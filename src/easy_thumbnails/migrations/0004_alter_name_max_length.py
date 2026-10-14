from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('easy_thumbnails', '0003_source_thumb_hash'),
    ]

    operations = [
        migrations.AlterField(
            model_name='source',
            name='name',
            field=models.CharField(db_index=True, max_length=512),
        ),
        migrations.AlterField(
            model_name='thumbnail',
            name='name',
            field=models.CharField(db_index=True, max_length=512),
        ),
    ]
