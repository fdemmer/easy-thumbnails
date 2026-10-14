from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from easy_thumbnails.alias import aliases
from easy_thumbnails.models import Source, ThumbnailDimensions
from easy_thumbnails.utils import get_storage_hash

from .forms import TestImageForm
from .models import TestImage


def index(request):
    if request.method == 'POST':
        form = TestImageForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('index')
    else:
        form = TestImageForm()
    images = list(TestImage.objects.all())
    for image in images:
        # the thumb_hash is stored when the first thumbnail is generated
        image.image['gallery']
        image.thumb_hash = image.image.get_thumb_hash()
    return render(request, 'mainapp/index.html', {'form': form, 'images': images})


def edit_image(request, pk):
    image = get_object_or_404(TestImage, pk=pk)
    if request.method == 'POST':
        form = TestImageForm(request.POST, request.FILES, instance=image)
        if form.is_valid():
            form.save()
            return redirect('index')
    else:
        form = TestImageForm(instance=image)
    return render(request, 'mainapp/edit_image.html', {'form': form, 'image': image})


def image_detail(request, pk):
    image = get_object_or_404(TestImage, pk=pk)
    field_file = image.image

    # alias renditions are only created on first access, make sure they exist
    for alias in aliases.all(target='mainapp.TestImage.image'):
        try:
            field_file[alias]
        except Exception:
            pass

    renditions = []
    source = Source.objects.get_file(field_file.storage, field_file.name)
    if source is not None:
        thumbnail_storage = field_file.thumbnail_storage
        thumbnails = source.thumbnails.filter(
            storage_hash=get_storage_hash(thumbnail_storage)
        ).select_related('dimensions')
        for thumbnail in thumbnails.order_by('name'):
            try:
                width, height = thumbnail.dimensions.size
            except ThumbnailDimensions.DoesNotExist:
                width = height = None
            try:
                size = thumbnail_storage.size(thumbnail.name)
            except OSError:
                size = None
            renditions.append(
                {
                    'size': size,
                    'name': thumbnail.name,
                    'url': thumbnail_storage.url(thumbnail.name),
                    'format': thumbnail.name.rsplit('.', 1)[-1],
                    'width': width,
                    'height': height,
                    'modified': thumbnail.modified,
                }
            )

    try:
        original_modified = field_file.storage.get_modified_time(field_file.name)
    except (OSError, NotImplementedError):
        original_modified = None
    try:
        original_size = field_file.size
    except OSError:
        original_size = None
    original = {
        'name': field_file.name,
        'url': field_file.url,
        'format': field_file.name.rsplit('.', 1)[-1],
        'width': image.image.width,
        'height': image.image.height,
        'size': original_size,
        'modified': original_modified,
    }

    return render(
        request,
        'mainapp/image_detail.html',
        {
            'image': image,
            'thumb_hash': field_file.get_thumb_hash(),
            'rows': [original] + renditions,
            'renditions': renditions,
        },
    )


@require_POST
def delete_image(request, pk):
    image = get_object_or_404(TestImage, pk=pk)
    image.delete()
    return redirect('index')
