# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Dev-only: hire types with PLACEHOLDER fees, meetings, techs, flag on.

Fees here are invented so the estimate has something to multiply. Replace
them with the real FAQ prices in Hire settings > Hire types before use.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from toolkit.diary.models import get_site_config
from toolkit.hires.models import (
    ApprovedTech,
    HireEnquiry,
    HireSettings,
    HireType,
    ProgrammingMeeting,
)

# name, community, corporate, unit, needs_sound_tech, provides_door_staff
TYPES = [
    ("Cinema screening", 120, 250, "flat", False, False),
    ("Gig or club night", 150, 300, "flat", True, True),
    ("Talk, workshop or meeting", 15, 30, "hour", False, False),
    ("Something else (tell us about it)", 100, 200, "flat", False, False),
]


class Command(BaseCommand):
    help = "Seed placeholder hire types and meetings; switch the flag on."

    def handle(self, *args, **opts):
        for i, (name, com, corp, unit, tech, door) in enumerate(TYPES):
            HireType.objects.get_or_create(
                name=name,
                defaults=dict(
                    community_fee_gbp=Decimal(com),
                    corporate_fee_gbp=Decimal(corp),
                    unit=unit,
                    needs_sound_tech=tech,
                    provides_door_staff=door,
                    order=i,
                ),
            )
        self._seed_meetings()
        self._seed_techs()
        cfg = HireSettings.load()
        if not cfg.notification_addresses:
            cfg.notification_addresses = "programming@example.org"
            cfg.save()
        site = get_site_config()
        site.hire_enquiries_enabled = True
        site.save()
        self._seed_menu()
        self.stdout.write("Seeded hire dev data; hire_enquiries_enabled on.")

    def _seed_meetings(self):
        """The two Monday meetings that discuss hires, for three months.

        Every meeting is a Monday at 6pm, a different one each week (see
        seed_data/recurring.toml). Only the 2nd Monday (Open Programming)
        and 4th Monday (Programme Development) take hire enquiries, so only
        those are entered here; Caretaking and the Open Meeting are not.
        """
        from toolkit.hires import services
        from toolkit.util.management.commands.seed_dev_data import (
            _nth_weekday_of_month,
        )

        today = timezone.localdate()
        wanted = []
        year, month = today.year, today.month
        for _ in range(4):
            for n, kind in ((2, "programming"), (4, "development")):
                day = _nth_weekday_of_month(year, month, 0, n)
                # No Programme Development over Christmas on the live site
                if day > today and not (month == 12 and n == 4):
                    wanted.append((day, kind))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        for day, kind in wanted:
            ProgrammingMeeting.objects.update_or_create(
                date=day, defaults={"kind": kind}
            )
        # Earlier seeds made meetings on any weekday; re-home their
        # enquiries before removing them
        dates = [d for d, _k in wanted]
        stray = ProgrammingMeeting.objects.filter(date__gt=today).exclude(
            date__in=dates
        )
        orphans = list(
            HireEnquiry.objects.filter(meeting__in=stray).values_list(
                "pk", flat=True
            )
        )
        stray.delete()
        for enquiry in HireEnquiry.objects.filter(pk__in=orphans):
            services.assign_meeting(enquiry)
            enquiry.save()

    def _seed_techs(self):
        """Made-up freelance sound techs (every name and number invented)."""
        for name, email, phone, rate, spec, share in [
            (
                "Ash Ferrier",
                "ash@example.org",
                "07700 900101",
                "£180 a night",
                "Live bands, the venue desk",
                True,
            ),
            (
                "Morgan Tully",
                "morgan@example.org",
                "07700 900202",
                "£150 a night, £90 for a talk",
                "Club nights, DJs, talks with mics",
                True,
            ),
            (
                "Sam Okonkwo-Reid",
                "sam@example.org",
                "",
                "Ask",
                "Folk and acoustic, small PA",
                False,
            ),
        ]:
            ApprovedTech.objects.get_or_create(
                name=name,
                defaults=dict(
                    email=email,
                    phone=phone,
                    rate_text=rate,
                    specialisms=spec,
                    share_with_hirers=share,
                    notes=(
                        ""
                        if share
                        else "Not yet asked about sharing details with hirers."
                    ),
                ),
            )

    def _seed_menu(self):
        """Mirror the live site's "Hire & Enquire" dropdown for local dev.

        An information page (edited in Wagtail, so no developer is needed to
        change hirer information) and a link to the enquiry form. On the
        live site, editors add the same link to the existing menu section.
        """
        from wagtail.models import Page, Site

        from toolkit.content.models import (
            BasicArticlePage,
            SectionLink,
            SectionRootWithLinks,
        )

        site = Site.objects.filter(is_default_site=True).first()
        root = site.root_page if site else Page.objects.filter(depth=2).first()
        if root is None:
            self.stdout.write(
                "No Wagtail home page yet (run seed_dev_data first): "
                "skipped the Hire & Enquire menu."
            )
            return
        section = Page.objects.filter(slug="hire-and-enquire").first()
        if section is None:
            section = SectionRootWithLinks(
                title="Hire & Enquire",
                slug="hire-and-enquire",
                live=True,
                show_in_menus=True,
            )
            root.add_child(instance=section)
        else:
            section = section.specific
        # Reset on every run, so a section left by an older seed (whose
        # "Enquire" pointed at the old Wagtail form) cannot keep a stale link
        SectionLink.objects.filter(page=section, text="Enquire").delete()
        SectionLink.objects.create(
            page=section, text="Enquire", link="/hires/enquire/"
        )
        from toolkit.util.seed_cms import ensure_page_image

        # Older seeds called the main hire page "FAQs"; rename it in place
        # so it keeps its spot at the top of the menu
        Page.objects.filter(slug="faqs", depth=section.depth + 1).update(
            slug="about-hiring",
            title="About hiring",
            url_path=section.url_path + "about-hiring/",
        )
        colours = {
            "about-hiring": "#0057B8",
            "technical-information": "#CC2200",
        }
        for title, slug, body in self._hire_pages():
            page = Page.objects.filter(
                slug=slug, depth=section.depth + 1
            ).first()
            if page is None:
                page = BasicArticlePage(
                    title=title,
                    slug=slug,
                    live=True,
                    show_in_menus=True,
                    body=body,
                )
                section.add_child(instance=page)
            else:
                # Refresh seeded copy so re-running picks up new content
                page = page.specific
                page.body = body
                page.save_revision().publish()
            ensure_page_image(
                page,
                f"Hire {title}",
                colours.get(slug, "#555555"),
                alignment="R" if slug == "about-hiring" else "C",
            )
        self._seed_legacy_form(section)

    def _hire_pages(self):
        """(title, slug, body) for the hirer-facing CMS pages.

        Prices come from TYPES so the page cannot drift from the form's
        price list. They are as invented as the fees themselves.
        """
        rows = "".join(
            f"<tr><td>{name}</td><td>£{com}</td><td>£{corp}</td>"
            f"<td>{'per hour' if unit == 'hour' else 'per booking'}</td></tr>"
            for name, com, corp, unit, _t, _d in TYPES
        )
        about = (
            "<p><em>Placeholder text for testing. On the live site editors "
            "own this page; hirers are sent here before they enquire.</em></p>"
            "<h3>Who we are</h3>"
            "<p>A volunteer-run charity cinema and arts space. Anyone with a "
            "good idea that fits our values can hire the building, and hires "
            "help pay for it and for the programme.</p>"
            "<h3>What we can offer</h3>"
            "<p>A cinema, a venue space for gigs, talks and club nights, and "
            "a café for meetings and small events. The "
            '<a href="/hire-and-enquire/technical-information/">technical '
            "information</a> page has the details of each space, including "
            "what to send us if you are showing a DCP.</p>"
            "<h3>What we can't do</h3>"
            "<p>Everyone working here is a volunteer. We guarantee the space "
            "and a keyholder; bar staff and anything else are best-effort. "
            "Late finishes are the exception: we have a limited number each "
            "year and they cost extra, and door staff are a separate charge "
            "for late club nights. Live music and club nights need an "
            "approved sound technician.</p>"
            "<h3>What does it cost?</h3>"
            "<table><thead><tr><th>Type of hire</th><th>Community rate</th>"
            "<th>Full rate</th><th>Charged</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
            "<p>The community rate is for unfunded, DIY, non-profit and "
            "charitable events. The full rate is for businesses, funded "
            "organisations and events run for profit. These are indicative: "
            "the form shows an estimate and we confirm the fee in writing "
            "before anything is booked.</p>"
            "<h3>What happens after I enquire?</h3>"
            "<ol><li>You send a short first enquiry.</li>"
            "<li>Volunteers discuss it at a programming meeting and reply "
            "with a yes, a no, or questions.</li>"
            "<li>After a yes in principle you get a link to give fuller "
            "details.</li>"
            "<li>You agree the terms with one click and the date is "
            "booked.</li></ol>"
            "<p>You will always get an answer, and we say how long it is "
            "likely to take.</p>"
            "<h3>Ready?</h3>"
            '<p><a class="btn btn-primary btn-lg" href="/hires/enquire/">'
            "Make an enquiry</a></p>"
            '<p>See also how we <a href="/hires/privacy/">look after your '
            "details</a>.</p>"
        )
        tech = (
            "<p><em>Placeholder text for testing.</em></p>"
            "<h3>Cinema</h3>"
            "<p>Digital projection, 5.1 sound, around 100 seats. A "
            "projectionist is arranged for you.</p>"
            "<h4>Sending us a DCP</h4>"
            "<p>Our projector's media block is a <strong>Dolby IMB, serial "
            "number DLB-IMB-0042-7731</strong> (made up for testing). "
            "Your DCP needs a KDM issued for that serial number, made out "
            "for the dates and times of your hire. Please send us the "
            "DCP and KDM at least a week ahead so we can test it; unencrypted "
            "DCPs need no KDM. Tell us about any special requirements in "
            "your enquiry.</p>"
            "<h3>Venue Space</h3>"
            "<p>Open floor with a small PA and stage lighting. Live music "
            "and club nights need an approved sound technician, which we "
            "can help you find.</p>"
            "<h3>Café</h3>"
            "<p>Good for meetings and small talks. Bring your own laptop; "
            "there is a screen and wifi.</p>"
            '<p><a class="btn btn-primary" href="/hires/enquire/">'
            "Ready? Make an enquiry</a></p>"
        )
        return [
            ("About hiring", "about-hiring", about),
            ("Technical information", "technical-information", tech),
        ]

    def _seed_legacy_form(self, section):
        """The old Wagtail hire form, as on the live site.

        Not in the menu. With the flag on it redirects to the new form, so
        a tester can follow /hire-and-enquire/enquire-old/ to see that.
        """
        from wagtail.models import Page

        from toolkit.content.models import EmailFormPage

        if Page.objects.filter(slug="enquire-old").exists():
            return
        section.add_child(
            instance=EmailFormPage(
                title="Enquire (old form)",
                slug="enquire-old",
                live=True,
                show_in_menus=False,
                to_address="programming@example.org",
                from_address="noreply@example.org",
                subject="Hire enquiry (old form)",
                intro="<p>Superseded by the new enquiry form.</p>",
            )
        )
