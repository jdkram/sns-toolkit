"""Diary data models, split per concern.

Cross-module ForeignKey/M2M targets use string references ("diary.ModelName")
so the submodules can be imported in any order without Python-level import
cycles; Django resolves them via the app registry.  Importers should use
``from toolkit.diary.models import X`` -- this package re-exports every public
name for back-compat with the old single-file models.py.
"""

# human-contributors: ["Jonny Kram"]; ai-contributors: ["glm-5.2"]; status: "#ai-input"

from .site_config import (
    DEFAULT_FILMS_START_BANNER_TEXT,
    SITE_CONFIG_FIELD_GROUPS,
    SiteConfiguration,
    get_site_config,
)
from .event import (
    Event,
    EventLink,
    EventTemplateLink,
    EventTermsRevision,
    Film,
)
from .budget import (
    BUDGET_CATEGORY_TEMPLATES,
    INCOME_CATEGORY_TEMPLATE,
    EventBudgetLine,
    sync_budget_lines_for_event,
)
from .finance import (
    PerformerRegistration,
    PRSPerformerEntry,
    SettlementLineItem,
    SettlementRevision,
    ShowingSettlement,
)
from .rota import (
    EventTemplate,
    EventTemplateRole,
    EventTemplateRoom,
    Role,
    RotaEntry,
)
from .showing import (
    FutureDateTimeField,
    Room,
    RoomBooking,
    Showing,
    ShowingQuerySet,
)
from .misc import (
    DiaryIdea,
    EventTag,
    EventTagQuerySet,
    MediaItem,
    PrintedProgramme,
    PrintedProgrammeQuerySet,
    VolunteerEventMark,
)

__all__ = [
    "BUDGET_CATEGORY_TEMPLATES",
    "DEFAULT_FILMS_START_BANNER_TEXT",
    "DiaryIdea",
    "Event",
    "EventBudgetLine",
    "EventLink",
    "EventTag",
    "EventTagQuerySet",
    "EventTemplate",
    "EventTemplateLink",
    "EventTemplateRole",
    "EventTemplateRoom",
    "EventTermsRevision",
    "Film",
    "FutureDateTimeField",
    "INCOME_CATEGORY_TEMPLATE",
    "MediaItem",
    "PRSPerformerEntry",
    "PerformerRegistration",
    "PrintedProgramme",
    "PrintedProgrammeQuerySet",
    "Role",
    "Room",
    "RoomBooking",
    "RotaEntry",
    "SITE_CONFIG_FIELD_GROUPS",
    "SettlementLineItem",
    "SettlementRevision",
    "Showing",
    "ShowingQuerySet",
    "ShowingSettlement",
    "SiteConfiguration",
    "VolunteerEventMark",
    "get_site_config",
    "sync_budget_lines_for_event",
]
