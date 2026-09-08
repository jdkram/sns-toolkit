# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"
"""Functional coverage for the building map: the floorplan page itself, room
notes, the loft inventory, and area photos. Previously untested beyond the
shared test_security.py auth-boundary checks (Chunk 10, quality pass)."""

import json
import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from toolkit.diary.models import get_site_config
from toolkit.labs.models import AreaPhoto, LoftItem, LoftItemPhoto, RoomNote
from .common import LabsTestsMixin
from .test_photo_uploads import TINY_VALID_JPEG, _cleanup_media_file


def _jpeg(name="test.jpg"):
    return SimpleUploadedFile(name, TINY_VALID_JPEG, content_type="image/jpeg")


class BuildingMapGateTests(LabsTestsMixin, TestCase):
    """Toggling SiteConfiguration.building_map_enabled off 404s the map,
    room notes, the loft inventory, and area photos alike — one flag for
    the whole feature, since the loft and area photos have no separate
    nav entry of their own."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.building_map_enabled = False
        cfg.save()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_floorplan_404s_when_disabled(self):
        response = self.client.get(reverse("labs-floorplan"))
        self.assertEqual(response.status_code, 404)

    def test_room_note_404s_when_disabled(self):
        response = self.client.get(
            reverse("labs-room-note", kwargs={"room_id": "room-cinema"})
        )
        self.assertEqual(response.status_code, 404)

    def test_loft_item_create_404s_when_disabled(self):
        response = self.client.post(
            reverse(
                "labs-loft-item-create",
                kwargs={"zone_id": "loft-raised-west"},
            ),
            data=json.dumps({"name": "Ladder"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_area_photo_upload_404s_when_disabled(self):
        response = self.client.post(
            reverse(
                "labs-area-photo-upload", kwargs={"area_id": "room-cinema"}
            ),
            data={"image": _jpeg()},
        )
        self.assertEqual(response.status_code, 404)

    def test_enabled_by_default(self):
        cfg = get_site_config()
        cfg.building_map_enabled = True
        cfg.save()
        response = self.client.get(reverse("labs-floorplan"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "labs/floorplan.html")


class FloorplanPageTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_get_renders_with_expected_context(self):
        response = self.client.get(reverse("labs-floorplan"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("room_sections", response.context)
        self.assertIn("loft_zone_sections", response.context)
        section_keys = {s["key"] for s in response.context["room_sections"]}
        self.assertEqual(section_keys, {"primary", "secondary", "circulation"})

    def test_notes_json_includes_existing_note(self):
        response = self.client.get(reverse("labs-floorplan"))
        notes = json.loads(response.context["notes_json"])
        self.assertIn("room-cinema", notes)
        self.assertEqual(notes["room-cinema"]["body"], "Mind the step")

    def test_notes_json_is_script_safe(self):
        """A room note containing `</script>` must not break out of the
        inline <script> block it's rendered into (stored XSS)."""
        self.note_cinema.body = "</script><script>alert(1)</script>"
        self.note_cinema.save()
        response = self.client.get(reverse("labs-floorplan"))
        self.assertNotIn("</script>", response.context["notes_json"])
        rendered = response.content.decode()
        self.assertNotIn("</script><script>alert(1)</script>", rendered)

    def test_loft_items_json_is_script_safe(self):
        LoftItem.objects.create(
            zone_id="loft-raised-west",
            name="</script><script>alert(1)</script>",
            added_by=self.user_admin,
        )
        response = self.client.get(reverse("labs-floorplan"))
        self.assertNotIn("</script>", response.context["loft_items_json"])

    def test_loft_items_json_includes_item(self):
        LoftItem.objects.create(
            zone_id="loft-raised-west",
            name="Old projector",
            added_by=self.user_admin,
        )
        response = self.client.get(reverse("labs-floorplan"))
        items = json.loads(response.context["loft_items_json"])
        names = [i["name"] for i in items["loft-raised-west"]]
        self.assertIn("Old projector", names)


class RoomNoteTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_get_existing_note(self):
        response = self.client.get(
            reverse("labs-room-note", kwargs={"room_id": "room-cinema"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["body"], "Mind the step")

    def test_get_missing_note_returns_empty(self):
        response = self.client.get(
            reverse("labs-room-note", kwargs={"room_id": "room-bar"})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["body"], "")
        self.assertIsNone(data["updated_by"])

    def test_post_creates_note(self):
        response = self.client.post(
            reverse("labs-room-note", kwargs={"room_id": "room-bar"}),
            data=json.dumps({"body": "New note"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        note = RoomNote.objects.get(room_id="room-bar")
        self.assertEqual(note.body, "New note")
        self.assertEqual(note.updated_by, self.user_vol)

    def test_post_updates_existing_note(self):
        self.client.post(
            reverse("labs-room-note", kwargs={"room_id": "room-cinema"}),
            data=json.dumps({"body": "Updated note"}),
            content_type="application/json",
        )
        self.note_cinema.refresh_from_db()
        self.assertEqual(self.note_cinema.body, "Updated note")

    def test_post_strips_whitespace(self):
        self.client.post(
            reverse("labs-room-note", kwargs={"room_id": "room-bar"}),
            data=json.dumps({"body": "  padded  "}),
            content_type="application/json",
        )
        note = RoomNote.objects.get(room_id="room-bar")
        self.assertEqual(note.body, "padded")

    def test_post_invalid_json_returns_400(self):
        response = self.client.post(
            reverse("labs-room-note", kwargs={"room_id": "room-bar"}),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class LoftItemTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_create_item(self):
        response = self.client.post(
            reverse(
                "labs-loft-item-create",
                kwargs={"zone_id": "loft-raised-west"},
            ),
            data=json.dumps({"name": "Ladder", "description": "Wooden"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        item = LoftItem.objects.get(name="Ladder")
        self.assertEqual(item.zone_id, "loft-raised-west")
        self.assertEqual(item.description, "Wooden")
        self.assertEqual(item.added_by, self.user_vol)

    def test_create_item_unknown_zone_404(self):
        response = self.client.post(
            reverse("labs-loft-item-create", kwargs={"zone_id": "not-a-zone"}),
            data=json.dumps({"name": "Ladder"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_create_item_invalid_json_400(self):
        response = self.client.post(
            reverse(
                "labs-loft-item-create",
                kwargs={"zone_id": "loft-raised-west"},
            ),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_create_item_missing_name_400(self):
        response = self.client.post(
            reverse(
                "labs-loft-item-create",
                kwargs={"zone_id": "loft-raised-west"},
            ),
            data=json.dumps({"name": "  "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(LoftItem.objects.exists())

    def test_update_item(self):
        item = LoftItem.objects.create(
            zone_id="loft-low-east", name="Box", added_by=self.user_admin
        )
        response = self.client.post(
            reverse("labs-loft-item", kwargs={"item_id": item.pk}),
            data=json.dumps({"name": "Bigger box", "description": "Full"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.name, "Bigger box")
        self.assertEqual(item.description, "Full")

    def test_update_item_blank_name_keeps_existing(self):
        item = LoftItem.objects.create(
            zone_id="loft-low-east", name="Box", added_by=self.user_admin
        )
        self.client.post(
            reverse("labs-loft-item", kwargs={"item_id": item.pk}),
            data=json.dumps({"name": "  "}),
            content_type="application/json",
        )
        item.refresh_from_db()
        self.assertEqual(item.name, "Box")

    def test_update_item_invalid_json_400(self):
        item = LoftItem.objects.create(
            zone_id="loft-low-east", name="Box", added_by=self.user_admin
        )
        response = self.client.post(
            reverse("labs-loft-item", kwargs={"item_id": item.pk}),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_item(self):
        item = LoftItem.objects.create(
            zone_id="loft-low-east", name="Box", added_by=self.user_admin
        )
        response = self.client.delete(
            reverse("labs-loft-item", kwargs={"item_id": item.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LoftItem.objects.filter(pk=item.pk).exists())

    def tearDown(self):
        for item in LoftItem.objects.all():
            for photo in item.photos.all():
                _cleanup_media_file(photo.image)


class LoftItemPhotoTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")
        self.item = LoftItem.objects.create(
            zone_id="loft-low-east", name="Box", added_by=self.user_admin
        )

    def tearDown(self):
        for photo in LoftItemPhoto.objects.all():
            _cleanup_media_file(photo.image)

    def test_upload_photo(self):
        response = self.client.post(
            reverse("labs-loft-item-photo", kwargs={"item_id": self.item.pk}),
            data={"image": _jpeg(), "caption": "Front view"},
        )
        self.assertEqual(response.status_code, 201)
        photo = LoftItemPhoto.objects.get(item=self.item)
        self.assertEqual(photo.caption, "Front view")
        self.assertEqual(photo.uploaded_by, self.user_vol)

    def test_upload_without_image_400(self):
        response = self.client.post(
            reverse("labs-loft-item-photo", kwargs={"item_id": self.item.pk}),
            data={"caption": "No file"},
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_non_image_rejected(self):
        not_an_image = SimpleUploadedFile(
            "test.jpg", b"not image data", content_type="image/jpeg"
        )
        response = self.client.post(
            reverse("labs-loft-item-photo", kwargs={"item_id": self.item.pk}),
            data={"image": not_an_image},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(LoftItemPhoto.objects.filter(item=self.item).exists())

    def test_delete_photo(self):
        photo = LoftItemPhoto.objects.create(
            item=self.item, image=_jpeg(), uploaded_by=self.user_admin
        )
        response = self.client.post(
            reverse("labs-loft-photo-delete", kwargs={"photo_id": photo.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LoftItemPhoto.objects.filter(pk=photo.pk).exists())


class AreaPhotoTests(LabsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def tearDown(self):
        for photo in AreaPhoto.objects.all():
            _cleanup_media_file(photo.image)

    def test_upload_creates_photo(self):
        response = self.client.post(
            reverse(
                "labs-area-photo-upload", kwargs={"area_id": "room-cinema"}
            ),
            data={"image": _jpeg()},
        )
        self.assertEqual(response.status_code, 201)
        photo = AreaPhoto.objects.get(area_id="room-cinema")
        self.assertEqual(photo.uploaded_by, self.user_vol)

    def test_upload_replaces_existing_photo(self):
        old = AreaPhoto.objects.create(
            area_id="room-cinema",
            image=_jpeg("old.jpg"),
            uploaded_by=self.user_admin,
        )
        old_path = old.image.path
        response = self.client.post(
            reverse(
                "labs-area-photo-upload", kwargs={"area_id": "room-cinema"}
            ),
            data={"image": _jpeg("new.jpg")},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            AreaPhoto.objects.filter(area_id="room-cinema").count(), 1
        )
        self.assertFalse(os.path.exists(old_path))

    def test_upload_without_image_400(self):
        response = self.client.post(
            reverse(
                "labs-area-photo-upload", kwargs={"area_id": "room-cinema"}
            ),
            data={},
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_non_image_rejected(self):
        not_an_image = SimpleUploadedFile(
            "test.jpg", b"not image data", content_type="image/jpeg"
        )
        response = self.client.post(
            reverse(
                "labs-area-photo-upload", kwargs={"area_id": "room-cinema"}
            ),
            data={"image": not_an_image},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            AreaPhoto.objects.filter(area_id="room-cinema").exists()
        )

    def test_delete_photo(self):
        AreaPhoto.objects.create(
            area_id="room-cinema", image=_jpeg(), uploaded_by=self.user_admin
        )
        response = self.client.post(
            reverse(
                "labs-area-photo-delete", kwargs={"area_id": "room-cinema"}
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            AreaPhoto.objects.filter(area_id="room-cinema").exists()
        )

    def test_delete_missing_photo_404(self):
        response = self.client.post(
            reverse("labs-area-photo-delete", kwargs={"area_id": "room-bar"})
        )
        self.assertEqual(response.status_code, 404)
