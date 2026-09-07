import logging


from django.conf import settings


# Shared utility method:

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _get_omdb_api_key() -> str:
    """Return the active OMDb API key: DB setting takes precedence over env var."""
    from toolkit.diary.models import get_site_config

    db_key = get_site_config().omdb_api_key.strip()
    return db_key or settings.OMDB_API_KEY


def _film_json(film) -> dict:
    """Serialise a Film instance to a JSON-safe dict for AJAX responses."""
    return {
        "id": film.pk,
        "imdb_id": film.imdb_id,
        "media_type": film.media_type,
        "title": film.title,
        "original_title": film.original_title,
        "year": film.year,
        "director": film.director,
        "runtime_minutes": film.runtime_minutes,
        "countries": film.countries,
        "languages": film.languages,
        "overview": film.overview,
        "poster_url": film.poster_url,
        "imdb_url": (
            f"https://www.imdb.com/title/{film.imdb_id}/"
            if film.imdb_id
            else ""
        ),
    }
