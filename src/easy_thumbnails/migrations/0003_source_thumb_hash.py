from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('easy_thumbnails', '0002_thumbnaildimensions'),
    ]

    operations = [
        migrations.AddField(
            model_name='source',
            name='thumb_hash',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
