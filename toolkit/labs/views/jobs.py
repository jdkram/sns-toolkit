from django.contrib import messages
from django.contrib.auth.decorators import login_required
from toolkit.toolkit_auth.decorators import (
    write_required_strict,
)
from django.db.models import Case, When, Value, IntegerField
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from django.utils import timezone

from ..models import (
    Job,
)
from .. import forms as lab_forms


def _urgency_order():
    return Case(
        When(urgency=Job.URGENCY_HIGH, then=Value(0)),
        When(urgency=Job.URGENCY_MEDIUM, then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )


@login_required
def job_list(request):
    open_jobs = (
        Job.objects.filter(resolved=False)
        .annotate(urgency_order=_urgency_order())
        .select_related("posted_by", "claimed_by")
        .order_by("urgency_order", "-posted_at")
    )
    done_jobs = (
        Job.objects.filter(resolved=True)
        .select_related("posted_by", "claimed_by")
        .order_by("-resolved_at")[:20]
    )
    return render(
        request,
        "labs/jobs.html",
        {
            "open_jobs": open_jobs,
            "done_jobs": done_jobs,
            "URGENCY_HIGH": Job.URGENCY_HIGH,
            "URGENCY_MEDIUM": Job.URGENCY_MEDIUM,
            "LOCATION_BUILDING": Job.LOCATION_BUILDING,
            "LOCATION_REMOTE": Job.LOCATION_REMOTE,
        },
    )


@login_required
@write_required_strict
def job_add(request):
    if request.method == "POST":
        form = lab_forms.JobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.posted_by = request.user
            job.save()
            messages.success(request, f"Job '{job.title}' added.")
            return redirect("labs-jobs")
    else:
        form = lab_forms.JobForm()
    return render(
        request, "labs/job_form.html", {"form": form, "action": "Add"}
    )


@login_required
@write_required_strict
def job_edit(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    if request.method == "POST":
        form = lab_forms.JobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, f"Job '{job.title}' updated.")
            return redirect("labs-jobs")
    else:
        form = lab_forms.JobForm(instance=job)
    return render(
        request,
        "labs/job_form.html",
        {"form": form, "job": job, "action": "Edit"},
    )


@login_required
@require_POST
def job_claim(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    if job.claimed_by is None:
        job.claimed_by = request.user
        job.save()
        messages.success(request, f"You've claimed '{job.title}'.")
    return redirect("labs-jobs")


@login_required
@require_POST
def job_unclaim(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    if job.claimed_by == request.user or request.user.has_perm(
        "toolkit.write"
    ):
        job.claimed_by = None
        job.save()
        messages.success(request, f"'{job.title}' unclaimed.")
    return redirect("labs-jobs")


@login_required
@require_POST
def job_resolve(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    job.resolved = True
    job.resolved_at = timezone.now()
    job.save()
    messages.success(request, f"'{job.title}' marked as resolved.")
    return redirect("labs-jobs")
