# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from toolkit.toolkit_auth.decorators import panopticon_required

from ..forms import InductionRequestAdminForm
from ..models import InductionRequest


@panopticon_required
def manage_access_needs_list(request):
    requests = InductionRequest.objects.exclude(
        status=InductionRequest.STATUS_PURGED
    )
    status_filter = request.GET.get("status")
    if status_filter:
        requests = requests.filter(status=status_filter)
    return render(
        request,
        "inductions/manage/access_needs_list.html",
        {
            "requests": requests,
            "status_choices": InductionRequest.STATUS_CHOICES,
            "current_status": status_filter,
        },
    )


@panopticon_required
def manage_access_needs_detail(request, request_id):
    req = get_object_or_404(InductionRequest, pk=request_id)
    if request.method == "POST":
        form = InductionRequestAdminForm(request.POST, instance=req)
        if form.is_valid():
            form.save()
            messages.success(request, "Request updated.")
            return redirect(
                "inductions:manage_access_needs_detail", request_id=request_id
            )
    else:
        form = InductionRequestAdminForm(instance=req)

    return render(
        request,
        "inductions/manage/access_needs_detail.html",
        {
            "req": req,
            "form": form,
        },
    )
