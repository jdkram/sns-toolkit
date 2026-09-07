from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST


from ..models import (
    AreaPhoto,
)
from .. import forms as lab_forms

# ── Area photos (one per room / loft zone) ────────────────────────────────────


@login_required
@require_POST
def area_photo_upload(request, area_id):
    if "image" not in request.FILES:
        return JsonResponse({"error": "No image file"}, status=400)
    form = lab_forms.AreaPhotoForm(request.POST, request.FILES)
    if not form.is_valid():
        errors = "; ".join(
            f"{field}: {', '.join(errs)}"
            for field, errs in form.errors.items()
        )
        return JsonResponse({"error": errors}, status=400)
    try:
        existing = AreaPhoto.objects.get(area_id=area_id)
        existing.image.delete(save=False)
        existing.delete()
    except AreaPhoto.DoesNotExist:
        pass
    photo = form.save(commit=False)
    photo.area_id = area_id
    photo.uploaded_by = request.user
    photo.save()
    return JsonResponse(
        {"url": photo.image.url, "uploaded_at": photo.uploaded_at.isoformat()},
        status=201,
    )


@login_required
@require_POST
def area_photo_delete(request, area_id):  # noqa: ARG001 -- view signature
    photo = get_object_or_404(AreaPhoto, area_id=area_id)
    photo.image.delete(save=False)
    photo.delete()
    return JsonResponse({"deleted": True})
