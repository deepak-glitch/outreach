"""LinkedIn selectors, isolated so layout drift is a one-file fix.

These were harvested via `playwright codegen` and WILL rot as LinkedIn ships
UI changes. When discover starts failing loud (zero cards on a page that
clearly has posts), re-run:

    playwright codegen "https://www.linkedin.com/search/results/content/?keywords=ai%20engineer"

set Posts + Past 24 hours by hand, and refresh the entries below. Prefer
role/attribute-based locators over codegen's brittle CSS chains.
"""

# Ordered fallback lists: first selector that matches wins.
POST_CARD = [
    "div.feed-shared-update-v2",
    "li.artdeco-card div[data-urn*='urn:li:activity']",
    "div[data-urn*='urn:li:activity']",
]

# Attribute on (or inside) the card that carries the activity URN.
URN_ATTR = "data-urn"
URN_HOLDER = ["[data-urn*='urn:li:activity']", "[data-id*='urn:li:activity']"]

POST_TEXT = [
    "div.update-components-text",
    "span.break-words",
]

AUTHOR_NAME = [
    "span.update-components-actor__title span[aria-hidden='true']",
    "span.update-components-actor__title",
]

AUTHOR_HEADLINE = [
    "span.update-components-actor__description",
]

SEE_MORE_BUTTON = [
    "button.feed-shared-inline-show-more-text__see-more-less-toggle",
    "button:has-text('…more')",
    "button:has-text('see more')",
]

# Interstitials that mean: stop the run cleanly, do not push.
NO_RESULTS_MARKERS = [
    "text=No results found",
    "text=Try different keywords",
]
RATE_LIMIT_MARKERS = [
    "text=Let's do a quick security check",
    "text=unusual activity",
    "text=You've reached the limit",
]
LOGIN_WALL_MARKERS = [
    "input#username",
    "text=Sign in to LinkedIn",
]
