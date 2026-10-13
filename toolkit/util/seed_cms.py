# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Dev-only helpers for seeding Wagtail content (images and forms)."""

import io

from django.core.files.images import ImageFile

# CC0 photos on Wikimedia Commons (each file page states the CC0 dedication),
# grouped by orientation so a layout slot gets a photo that crops cleanly.
# Fetched once into the seed cache; offline, flat-colour images are used.
_PHOTOS = {
    "wide": [
        "Panorama of an IMAX 15 70 mm Film Projector.jpg",
        "Le Badaboum Paris concert stage.jpg",
        "Lumiere Cinema Romford.jpg",
        "Recording a concert (Unsplash).jpg",
    ],
    "portrait": [
        "Film Reel on an IMAX 15 70 mm Film Projector 2.jpg",
        "Schoolhouse Cinema Entrance.jpg",
        "Cafe Interior with Coffee.jpg",
        "Popcorn img.jpg",
    ],
    "square": [
        "Gordon Craig Theatre Auditorium.jpg",
        "Interior of Caf\u00e9 Belchers 2023-07-24.jpg",
        "Film Reel on an IMAX 15 70 mm Film Projector.jpg",
        "Popcorn in a bowl.jpg",
    ],
}
_PHOTO_CACHE = "/site/.seed_cache/images"
_UA = "sns-toolkit-dev-seed/1.0 (local dev data; CC0 images)"


def _photo_for(title, width, height):
    """PIL image of a CC0 photo cropped to width x height, or None."""
    import os
    import urllib.parse
    import urllib.request
    import zlib

    from PIL import Image as PILImage, ImageOps

    ratio = width / height
    kind = "wide" if ratio > 1.4 else "portrait" if ratio < 0.8 else "square"
    names = _PHOTOS[kind]
    name = names[zlib.crc32(title.encode()) % len(names)]
    try:
        os.makedirs(_PHOTO_CACHE, exist_ok=True)
        path = os.path.join(
            _PHOTO_CACHE, "cc0-" + name.replace(" ", "_").replace("/", "_")
        )
        if not os.path.exists(path):
            url = (
                "https://commons.wikimedia.org/wiki/Special:FilePath/"
                + urllib.parse.quote(name)
                + "?width=1600"
            )
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            with open(path, "wb") as fh:
                fh.write(data)
        with PILImage.open(path) as src:
            src = ImageOps.exif_transpose(src).convert("RGB")
            return ImageOps.fit(src, (width, height))
    except Exception:  # offline, blocked, or a bad file: fall back
        return None


def placeholder_image(title, colour, width=1200, height=675):
    """A Wagtail image for `title`: a CC0 photo, else a flat colour block.

    Created once per title. A flat-colour image from an earlier (offline)
    run is upgraded to a photo when one becomes available.
    """
    from PIL import Image as PILImage, ImageDraw
    from wagtail.images.models import Image
    from wagtail.models import Collection

    # A dev DB whose Wagtail tables were cleared has no root collection.
    if Collection.get_first_root_node() is None:
        Collection.add_root(name="Root")

    existing = Image.objects.filter(title=title).first()
    if existing is not None and not existing.file.name.split("/")[
        -1
    ].startswith("placeholder-"):
        return existing
    pil = _photo_for(title, width, height)
    is_photo = pil is not None
    if existing is not None and not is_photo:
        return existing
    if pil is None:
        pil = PILImage.new("RGB", (width, height), colour)
        draw = ImageDraw.Draw(pil)
        draw.line([(0, 0), (width, height)], fill=(255, 255, 255), width=3)
        draw.line([(0, height), (width, 0)], fill=(255, 255, 255), width=3)
        draw.text(
            (20, 20), f"{title} ({width}x{height})", fill=(255, 255, 255)
        )
    buf = io.BytesIO()
    pil.save(buf, "JPEG", quality=80)
    slug = title.lower().replace(" ", "-")
    prefix = "photo" if is_photo else "placeholder"
    image = existing or Image(title=title)
    image.file.save(
        f"{prefix}-{slug}.jpg", ImageFile(buf, name="p.jpg"), save=False
    )
    image.save()
    image.renditions.all().delete()
    return image


def ensure_page_image(page, title, colour, alignment="L", **size):
    """Attach a placeholder image to a BasicArticlePage if it has none."""
    if page.image_id:
        return
    page.image = placeholder_image(title, colour, **size)
    page.image_alignment = alignment
    page.save_revision().publish()


def seed_gallery_and_form(parent):
    """A gallery page and a native Wagtail form page under `parent`."""
    from wagtail.models import Page

    from toolkit.content.models import (
        EmailFormPage,
        ImageGalleryImage,
        ImageGalleryPage,
    )

    if not Page.objects.filter(slug="gallery").exists():
        gallery = ImageGalleryPage(
            title="Gallery",
            slug="gallery",
            live=True,
            show_in_menus=True,
            intro_text="<p>Placeholder images for testing layouts.</p>",
            footer_text="<p>Photos: nobody, they are flat colours.</p>",
        )
        parent.add_child(instance=gallery)
        sizes = [(1200, 675), (600, 900), (900, 900), (1600, 600)]
        colours = ["#CC2200", "#0057B8", "#2E8B57", "#8B5FBF", "#D98E04"]
        for i in range(6):
            w, h = sizes[i % len(sizes)]
            ImageGalleryImage.objects.create(
                page=gallery,
                image=placeholder_image(
                    f"Gallery {i + 1}", colours[i % len(colours)], w, h
                ),
                caption=f"Caption for picture {i + 1}",
            )
        gallery.save_revision().publish()

    if not Page.objects.filter(slug="get-in-touch").exists():
        form = EmailFormPage(
            title="Get in touch",
            slug="get-in-touch",
            live=True,
            show_in_menus=True,
            to_address="info@example.org",
            from_address="noreply@example.org",
            subject="Message from the website (dev)",
            intro="<p>A native Wagtail form (email form page): fields are "
            "edited in the CMS, submissions are emailed and also listed "
            "under Forms in the Wagtail admin.</p>",
            thank_you_text="<p>Thanks, we'll be in touch.</p>",
            image=placeholder_image("Form header", "#444444", 800, 400),
        )
        parent.add_child(instance=form)
        fields = [
            ("Your name", "singleline", True, ""),
            ("Your email", "email", True, ""),
            (
                "What is this about?",
                "dropdown",
                True,
                "General question,Volunteering,Press,Something else",
            ),
            ("Message", "multiline", True, ""),
            ("Please reply by email", "checkbox", False, ""),
        ]
        for i, (label, ftype, req, choices) in enumerate(fields):
            form.form_fields.create(
                sort_order=i,
                label=label,
                field_type=ftype,
                required=req,
                choices=choices,
            )
        form.save_revision().publish()


def _img(title, colour, w, h, alt=None):
    image = placeholder_image(title, colour, w, h)
    return {
        "type": "image",
        "value": {
            "image": image.pk,
            "decorative": alt is None,
            "alt_text": alt or "",
        },
    }


def _text(html):
    return {"type": "rich_text", "value": html}


def _block(width, *content):
    return {
        "type": "content_block",
        "value": {"width": width, "content": list(content)},
    }


_LOREM = (
    "<h3>{h}</h3><p>Placeholder copy to show how text wraps at this width. "
    "Star and Shadow is a volunteer-run cinema, and this paragraph is "
    "standing in for whatever an editor writes. Lorem ipsum dolor sit "
    "amet, consectetur adipiscing elit, sed do eiusmod tempor.</p>"
    "<p>A second paragraph, so the column has some length to compare "
    "against its neighbours.</p>"
)


def _complex_layouts():
    """(title, slug, stream) for ComplexArticlePage layout examples.

    Widths are grid columns, 1 to 5; 5 is the full width of the page grid.
    """
    wide = lambda t, c: _img(t, c, 1600, 600, alt=t)  # noqa: E731
    return [
        (
            "Layout: full-width banner",
            "layout-full-width-banner",
            [
                _block(5, wide("Full-width banner", "#CC2200")),
                _block(5, _text(_LOREM.format(h="Full-width text"))),
                _block(5, wide("Second full-width image", "#0057B8")),
            ],
        ),
        (
            "Layout: text beside image",
            "layout-text-beside-image",
            [
                _block(3, _text(_LOREM.format(h="Text, three columns"))),
                _block(
                    2, _img("Portrait 2-col", "#2E8B57", 600, 900, "Portrait")
                ),
                _block(2, _img("Square 2-col", "#8B5FBF", 800, 800, "Square")),
                _block(3, _text(_LOREM.format(h="Image on the left"))),
            ],
        ),
        (
            "Layout: three-up images",
            "layout-three-up-images",
            [
                _block(
                    5, _text("<h3>Three-up</h3><p>Small tiles in a row.</p>")
                ),
                _block(1, _img("Tile 1", "#D98E04", 400, 400, "Tile one")),
                _block(2, _img("Tile 2", "#CC2200", 800, 800, "Tile two")),
                _block(2, _img("Tile 3", "#0057B8", 800, 800, "Tile three")),
            ],
        ),
        (
            "Layout: magazine mix",
            "layout-magazine-mix",
            [
                _block(5, wide("Magazine banner", "#444444")),
                _block(2, _text(_LOREM.format(h="Left column"))),
                _block(
                    3,
                    _img("Magazine feature", "#2E8B57", 1200, 900, "Feature"),
                ),
                _block(3, _text(_LOREM.format(h="Wider column"))),
                _block(2, _img("Magazine tall", "#8B5FBF", 600, 1000, "Tall")),
                _block(5, _text(_LOREM.format(h="Closing full-width text"))),
            ],
        ),
        (
            "Layout: embeds and quotes",
            "layout-embeds-and-quotes",
            [
                _block(
                    5,
                    {
                        "type": "raw_html",
                        "value": "<blockquote><p>“A pull quote set in "
                        "raw HTML, full width.”</p></blockquote>",
                    },
                ),
                _block(
                    3,
                    {
                        "type": "raw_html",
                        "value": '<div style="background:#eee;padding:2em;'
                        'text-align:center">Embed placeholder (e.g. a '
                        "video player)</div>",
                    },
                ),
                _block(2, _text(_LOREM.format(h="Caption column"))),
            ],
        ),
    ]


def seed_layout_examples(parent):
    """A "Layout Examples" menu section: every image/text arrangement."""
    from wagtail.models import Page

    from toolkit.content.models import (
        BasicArticlePage,
        ComplexArticlePage,
        SectionLink,
        SectionRootWithLinks,
    )

    if Page.objects.filter(slug="layout-examples").exists():
        return
    section = SectionRootWithLinks(
        title="Layout Examples",
        slug="layout-examples",
        live=True,
        show_in_menus=True,
    )
    parent.add_child(instance=section)
    SectionLink.objects.create(page=section, text="Gallery", link="/gallery/")

    body = _LOREM.format(h="Body")[len("<h3>Body</h3>") :]
    for title, slug, align, colour in [
        ("Layout: image left", "layout-image-left", "L", "#0057B8"),
        ("Layout: image right", "layout-image-right", "R", "#CC2200"),
        ("Layout: image centred", "layout-image-centred", "C", "#2E8B57"),
        ("Layout: no image", "layout-no-image", "L", None),
    ]:
        page = BasicArticlePage(
            title=title,
            slug=slug,
            live=True,
            show_in_menus=True,
            body=body,
            image_alignment=align,
            image=(
                placeholder_image(title, colour, 1200, 800) if colour else None
            ),
        )
        section.add_child(instance=page)

    for title, slug, stream in _complex_layouts():
        section.add_child(
            instance=ComplexArticlePage(
                title=title,
                slug=slug,
                live=True,
                show_in_menus=True,
                content=stream,
            )
        )


def upgrade_placeholder_images():
    """Swap flat-colour seed images for CC0 photos where one can be fetched."""
    from wagtail.images.models import Image

    for image in Image.objects.filter(file__contains="placeholder-"):
        placeholder_image(image.title, "#555555", image.width, image.height)
