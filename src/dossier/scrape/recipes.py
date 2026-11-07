"""Capture recipes: a workflow as data, validated before anything opens a socket.

A recipe is the maintainable half of the scraping system. The engine owns the
mechanics (policy, pacing, retries, extraction, receipts); a recipe owns only the
site-specific part — where the list is, what to call each field, how the next page
is addressed — so teaching Dossier a new board is a JSON file, not a code change.

Validation is strict on purpose. `MAX_KEYS` is closed: an unrecognised top-level
key is an error rather than a note, because a typo (`"paginaton"`) otherwise
silently means "one page and a partial capture reported as complete", which is the
one outcome the `partial-is-not-exhaustive` gate exists to prevent. Selectors are
checked by *parsing* them rather than by a regex, so a selector that lxml rejects
fails here instead of halfway through a live run.

Recipes live in two places, workspace first:

* `.dossier/scrapes/*.json` — this folder's own workflows, including overrides of
  a shipped recipe with the same `id`.
* `templates/scrapes/*.json` — the shipped examples, which are also the format's
  documentation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .errors import RecipeError

WORKSPACE_DIR = ".dossier/scrapes"
SHIPPED_DIR = "templates/scrapes"

TOP_KEYS = {
    "id", "source", "start_url", "auth", "list", "detail", "pagination", "limits",
    "cadence_hours", "headless", "robots", "wait_until", "wait_selector", "notes",
    "title", "company", "location", "pay", "search", "challenge",
}
LIST_KEYS = {"item", "link", "title", "company", "location", "pay"}
DETAIL_KEYS = {"content", "remove"}
PAGINATION_KEYS = {"mode", "param", "start", "max_pages", "selector"}
LIMIT_KEYS = {"max_items", "delay_ms", "timeout_s", "retries", "await_seconds", "min_match"}
PAGINATION_MODES = ("none", "query", "next-link")
AUTH_MODES = ("public", "required")
WAIT_UNTIL = ("load", "domcontentloaded", "networkidle", "commit")


@dataclass(frozen=True)
class Recipe:
    id: str
    source: str
    start_url: str
    auth: str = "public"
    list: dict = field(default_factory=dict)
    detail: dict = field(default_factory=dict)
    pagination: dict = field(default_factory=dict)
    limits: dict = field(default_factory=dict)
    cadence_hours: float = 0
    headless: bool = True
    robots: bool = True
    wait_until: str = "load"
    wait_selector: str = ""
    notes: str = ""
    challenge: str = "auto"
    path: str = ""
    origin: str = "workspace"

    # -- convenience -------------------------------------------------------
    @property
    def is_list(self) -> bool:
        """A list recipe walks items; a single recipe captures one page."""
        return bool(self.list.get("item"))

    @property
    def max_items(self) -> int:
        return int(self.limits.get("max_items", 25))

    @property
    def max_pages(self) -> int:
        return int(self.pagination.get("max_pages", 1))

    @property
    def delay_ms(self) -> int:
        return int(self.limits.get("delay_ms", 1500))

    @property
    def timeout_s(self) -> float:
        return float(self.limits.get("timeout_s", 30))

    @property
    def retries(self) -> int:
        return int(self.limits.get("retries", 2))

    @property
    def min_match(self) -> int:
        """Relevance floor for an archived item; 0 archives everything."""
        return int(self.limits.get("min_match", 0))

    @property
    def await_seconds(self) -> float:
        """How long a challenge page may be given to clear on its own."""
        return float(self.limits.get("await_seconds", 0))

    def to_dict(self) -> dict:
        return asdict(self)


def _selector_ok(value: str, where: str) -> None:
    try:
        from lxml.cssselect import CSSSelector
        CSSSelector(value)
    except Exception as exc:  # noqa: BLE001 - any parse failure is the same answer
        raise RecipeError(f"{where}: {value!r} is not a selector lxml accepts ({exc})") from None


def _number(value, where: str, *, low: float, high: float, integer: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RecipeError(f"{where} must be a number, got {value!r}")
    if not (low <= value <= high):
        raise RecipeError(f"{where} must be between {low:g} and {high:g}, got {value!r}")
    return value if not integer else int(value)


def validate(data: dict, *, path: str = "") -> Recipe:
    """Turn a parsed recipe into a `Recipe`, or raise with the exact reason it cannot run."""
    if not isinstance(data, dict):
        raise RecipeError(f"{path or 'recipe'} must be a JSON object, got {type(data).__name__}")

    unknown = sorted(set(data) - TOP_KEYS)
    if unknown:
        raise RecipeError(
            f"{path or 'recipe'} has unknown key(s) {unknown}. Accepted top-level keys: "
            f"{sorted(TOP_KEYS)}. A misspelled section would otherwise silently mean "
            "'one page'.")

    recipe_id = str(data.get("id") or "").strip()
    if not recipe_id:
        raise RecipeError(f"{path or 'recipe'} needs an 'id'")
    if not all(ch.isalnum() or ch in "-_" for ch in recipe_id):
        raise RecipeError(f"{path or 'recipe'}: id {recipe_id!r} may only use letters, digits, '-' and '_'")

    source = str(data.get("source") or "").strip().casefold()
    if not source:
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}) needs a 'source' naming the board")

    url = str(data.get("start_url") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RecipeError(
            f"{path or 'recipe'} ({recipe_id}): start_url must be an absolute http(s) URL, "
            f"got {url!r}")

    auth = str(data.get("auth") or "public").strip().casefold()
    if auth not in AUTH_MODES:
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): auth must be one of {AUTH_MODES}")

    wait_until = str(data.get("wait_until") or "load").strip()
    if wait_until not in WAIT_UNTIL:
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): wait_until must be one of {WAIT_UNTIL}")

    listing = data.get("list") or {}
    if not isinstance(listing, dict):
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): 'list' must be an object")
    unknown_list = sorted(set(listing) - LIST_KEYS)
    if unknown_list:
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): unknown 'list' key(s) {unknown_list}; "
                          f"accepted: {sorted(LIST_KEYS)}")
    if listing:
        if not str(listing.get("item") or "").strip():
            raise RecipeError(f"{path or 'recipe'} ({recipe_id}): a 'list' section needs 'item'")
        for field_name, value in listing.items():
            if value in (None, ""):
                continue
            _selector_ok(str(value), f"{path or 'recipe'} ({recipe_id}) list.{field_name}")
        if not str(listing.get("link") or "").strip():
            raise RecipeError(f"{path or 'recipe'} ({recipe_id}): a 'list' needs a 'link' selector "
                              "so each item can be opened")

    detail = data.get("detail") or {}
    if not isinstance(detail, dict):
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): 'detail' must be an object")
    unknown_detail = sorted(set(detail) - DETAIL_KEYS)
    if unknown_detail:
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): unknown 'detail' key(s) "
                          f"{unknown_detail}; accepted: {sorted(DETAIL_KEYS)}")
    if detail.get("content"):
        _selector_ok(str(detail["content"]), f"{path or 'recipe'} ({recipe_id}) detail.content")
    removes = detail.get("remove") or []
    if not isinstance(removes, list):
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): detail.remove must be a list")
    for selector in removes:
        _selector_ok(str(selector), f"{path or 'recipe'} ({recipe_id}) detail.remove")

    pagination = data.get("pagination") or {}
    if not isinstance(pagination, dict):
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): 'pagination' must be an object")
    unknown_pagination = sorted(set(pagination) - PAGINATION_KEYS)
    if unknown_pagination:
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): unknown 'pagination' key(s) "
                          f"{unknown_pagination}; accepted: {sorted(PAGINATION_KEYS)}")
    mode = str(pagination.get("mode") or "none").strip()
    if mode not in PAGINATION_MODES:
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): pagination.mode must be one of "
                          f"{PAGINATION_MODES}")
    if mode == "query" and not str(pagination.get("param") or "").strip():
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): pagination.mode 'query' needs a 'param'")
    if mode == "next-link" and not str(pagination.get("selector") or "").strip():
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): pagination.mode 'next-link' needs "
                          "a 'selector' for the next-page anchor")
    if mode == "query":
        _number(pagination.get("start", 1), f"{path or 'recipe'} ({recipe_id}) pagination.start",
                low=0, high=1000)
    _number(pagination.get("max_pages", 1) if pagination else 1,
            f"{path or 'recipe'} ({recipe_id}) pagination.max_pages", low=1, high=50)

    limits = data.get("limits") or {}
    if not isinstance(limits, dict):
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): 'limits' must be an object")
    unknown_limits = sorted(set(limits) - LIMIT_KEYS)
    if unknown_limits:
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): unknown 'limits' key(s) "
                          f"{unknown_limits}; accepted: {sorted(LIMIT_KEYS)}")
    _number(limits.get("max_items", 25), f"{path or 'recipe'} ({recipe_id}) limits.max_items",
            low=1, high=500)
    _number(limits.get("delay_ms", 1500), f"{path or 'recipe'} ({recipe_id}) limits.delay_ms",
            low=0, high=300_000)
    _number(limits.get("timeout_s", 30), f"{path or 'recipe'} ({recipe_id}) limits.timeout_s",
            low=1, high=300, integer=False)
    _number(limits.get("retries", 2), f"{path or 'recipe'} ({recipe_id}) limits.retries",
            low=0, high=5)
    _number(limits.get("await_seconds", 0),
            f"{path or 'recipe'} ({recipe_id}) limits.await_seconds", low=0, high=300,
            integer=False)
    _number(limits.get("min_match", 0),
            f"{path or 'recipe'} ({recipe_id}) limits.min_match", low=0, high=100)

    from .challenge import POLICIES
    challenge = str(data.get("challenge") or "auto").strip()
    if challenge not in POLICIES:
        raise RecipeError(f"{path or 'recipe'} ({recipe_id}): challenge must be one of {POLICIES}")

    cadence = data.get("cadence_hours", 0)
    _number(cadence, f"{path or 'recipe'} ({recipe_id}) cadence_hours", low=0, high=24 * 90,
            integer=False)

    for flag in ("headless", "robots"):
        if flag in data and not isinstance(data[flag], bool):
            raise RecipeError(f"{path or 'recipe'} ({recipe_id}): {flag} must be true or false")

    return Recipe(
        id=recipe_id,
        source=source,
        start_url=url,
        auth=auth,
        list={key: str(value) for key, value in listing.items() if value not in (None, "")},
        detail={"content": str(detail.get("content") or ""),
                "remove": [str(item) for item in removes]},
        pagination={"mode": mode,
                    "param": str(pagination.get("param") or ""),
                    "start": int(pagination.get("start", 1)),
                    "max_pages": int(pagination.get("max_pages", 1) if pagination else 1),
                    "selector": str(pagination.get("selector") or "")},
        limits={"max_items": int(limits.get("max_items", 25)),
                "delay_ms": int(limits.get("delay_ms", 1500)),
                "timeout_s": float(limits.get("timeout_s", 30)),
                "retries": int(limits.get("retries", 2)),
                "await_seconds": float(limits.get("await_seconds", 0)),
                "min_match": int(limits.get("min_match", 0))},
        cadence_hours=float(cadence),
        headless=bool(data.get("headless", True)),
        robots=bool(data.get("robots", True)),
        wait_until=wait_until,
        wait_selector=str(data.get("wait_selector") or ""),
        notes=str(data.get("notes") or ""),
        challenge=challenge,
        path=path,
        origin=str(data.get("origin") or "workspace"),
    )


def load(path: Path | str) -> Recipe:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RecipeError(f"no recipe at {path}") from None
    except ValueError as exc:
        raise RecipeError(f"{path.name} is not valid JSON: {exc}") from None
    recipe = validate(data, path=str(path))
    return recipe.__class__(**{**recipe.to_dict(), "path": str(path),
                               "origin": recipe.origin})


def recovery(root: Path | str) -> dict:
    """.dossier/scrapes/*.json and templates/scrapes/*.json, for a status report."""
    root = Path(root)
    return {
        "workspace": str(root / WORKSPACE_DIR),
        "shipped": str(Path(__file__).parents[3] / SHIPPED_DIR),
        "workspace_files": sorted((root / WORKSPACE_DIR).glob("*.json")) if (root / WORKSPACE_DIR).is_dir() else [],
        "shipped_files": sorted((Path(__file__).parents[3] / SHIPPED_DIR).glob("*.json")),
    }


def discover(root: Path | str, *, include_shipped: bool = True) -> tuple[list[Recipe], list[dict]]:
    """Every runnable recipe plus the failures, workspace first, id-unique.

    A broken workspace recipe is reported, never silently replaced by the shipped
    one with the same id: the workspace file is the user's intent, and a silent
    fallback would run a workflow they did not write.
    """
    found: dict[str, Recipe] = {}
    errors: list[dict] = []
    broken_ids: set[str] = set()
    root = Path(root)

    def read(path: Path, origin: str) -> None:
        try:
            recipe = load(path)
        except RecipeError as exc:
            errors.append({"path": str(path), "error": str(exc)})
            broken_ids.add(path.stem)
            return
        if recipe.id in found and origin == "workspace":
            errors.append({"path": str(path),
                           "error": f"duplicate recipe id {recipe.id!r}; "
                                    "the first workspace file with this id wins"})
            return
        found[recipe.id] = Recipe(**{**recipe.to_dict(), "path": str(path), "origin": origin})

    for path in recovery(root)["workspace_files"]:
        read(path, "workspace")
    if include_shipped:
        for path in recovery(root)["shipped_files"]:
            # A broken workspace file is the user's intent. Substituting the shipped
            # recipe with the same id would run a workflow they did not write.
            if path.stem in found or path.stem in broken_ids:
                continue
            read(path, "shipped")
    return [found[key] for key in sorted(found)], errors


__all__ = ["AUTH_MODES", "PAGINATION_MODES", "Recipe", "WORKSPACE_DIR", "discover", "load",
           "recovery", "validate"]
