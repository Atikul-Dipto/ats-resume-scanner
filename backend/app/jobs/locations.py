"""Is a job reachable for a candidate in Bangladesh?

"Remote" alone isn't enough: most remote roles are restricted to a country
or region ("Remote, Canada", "Remote (EMEA)", "USA, Remote"). A remote job
counts only when it's unrestricted or names a region that includes
Bangladesh; an on-site job counts when it's in Bangladesh.
"""

import re

BANGLADESH_RE = re.compile(
    r"\b(bangladesh|dhaka|chattogram|chittagong|sylhet|khulna|rajshahi|barishal|barisal|rangpur|"
    r"mymensingh|gazipur|narayanganj|savar|cumilla|comilla|bogura|bogra|ashulia|tongi)\b",
    re.IGNORECASE,
)
REMOTE_RE = re.compile(r"\b(remote|anywhere|worldwide|work from home|wfh|distributed|home[- ]based)\b", re.IGNORECASE)
OPEN_REGION_RE = re.compile(
    r"\b(worldwide|anywhere|global|globally|international|apac|asia|south asia|asia[- ]pacific|"
    r"all locations|any location|emea & apac)\b",
    re.IGNORECASE,
)
# Words that describe *how* the job is remote, not *where* — removing them
# leaves an empty string for an unrestricted "Remote" / "Fully remote".
_REMOTE_FILLER_RE = re.compile(
    r"\b(remote|fully|100%|work from home|wfh|distributed|home[- ]based|based|first|friendly|option|optional|"
    r"available|ok|position|role|team|global?)\b|[()\[\],;:/|&+\-–—.]",
    re.IGNORECASE,
)


def is_remote(location: str, remote_flag: bool | None = None) -> bool:
    return bool(remote_flag) or bool(REMOTE_RE.search(location or ""))


def in_bangladesh(location: str) -> bool:
    return bool(BANGLADESH_RE.search(location or ""))


def remote_open_to_bangladesh(location: str) -> bool:
    location = location or ""
    if in_bangladesh(location) or OPEN_REGION_RE.search(location):
        return True
    return not _REMOTE_FILLER_RE.sub(" ", location).strip()


def reachable_from_bangladesh(location: str, remote_flag: bool | None = None) -> bool:
    if in_bangladesh(location):
        return True
    return is_remote(location, remote_flag) and remote_open_to_bangladesh(location)
