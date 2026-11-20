"""Collect only public frontend assets; never publish Python code or .env files."""
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.finders import BaseFinder
from django.core.files.storage import FileSystemStorage

ROOT = Path(__file__).resolve().parent.parent

# Existing UI folders that contain files needed by the browser.
PAGE_FOLDERS = (
    "skillbridge_public_landing_page",
    "skillbridge_certificates_achievements",
    "skillbridge_course_details_learning_experience",
    "skillbridge_courses_catalogue",
    "skillbridge_opportunities_career_discovery",
    "skillbridge_practical_projects",
    "skillbridge_skill_pathways_career_roadmaps",
    "skillbridge_student_analytics_learning_progress",
    "skillbridge_student_dashboard",
    "skillbridge_student_dashboard_fidelity",
    "skillbridge_student_portfolio",
    "ucc_skillshub_courses_catalogue",
    "ucc_skillshub_sign_in",
    "ucc_skillshub_student_dashboard",
)
PUBLIC_EXTENSIONS = {".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".woff", ".woff2"}


def frontend_asset(path):
    """Return a public asset file, not arbitrary repository files."""
    if not path or "\\" in path or any(p in ("", ".", "..") for p in path.split("/")):
        return None
    relative = Path(path)
    if relative.suffix.lower() not in PUBLIC_EXTENSIONS:
        return None
    if len(relative.parts) == 1:
        # Root JS and CSS only; images reside under the named UI folders.
        if relative.suffix.lower() not in {".js", ".css"}:
            return None
    elif relative.parts[0] not in PAGE_FOLDERS:
        return None
    candidate = (ROOT / relative).resolve()
    if not candidate.is_relative_to(ROOT) or not candidate.is_file():
        return None
    return candidate


class FrontendStaticFinder(BaseFinder):
    """Expose the existing UI's CSS, JS and images to collectstatic/Vercel CDN."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage = FileSystemStorage(location=str(ROOT))

    def find(self, path, find_all=False):
        candidate = frontend_asset(path)
        if find_all:
            return [str(candidate)] if candidate else []
        return str(candidate) if candidate else None

    def list(self, ignore_patterns):
        candidates = list(ROOT.glob("*.js")) + list(ROOT.glob("*.css"))
        for folder in PAGE_FOLDERS:
            directory = ROOT / folder
            if directory.is_dir():
                candidates.extend(directory.rglob("*"))
        for candidate in candidates:
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(ROOT).as_posix()
            if frontend_asset(relative) and not any(
                candidate.match(pattern) for pattern in ignore_patterns
            ):
                yield relative, self.storage
