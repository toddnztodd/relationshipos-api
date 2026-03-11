"""Default 12-phase listing checklist templates by sale method."""

import copy

PHASE_NAMES = {
    1: "Pre-Appraisal / Pre-Listing",
    2: "Appraisal Complete",
    3: "Listing Agreement Signed",
    4: "Compliance / File Setup",
    5: "Marketing Preparation",
    6: "Campaign Live",
    7: "Open Homes / Buyer Activity",
    8: "Offers / Negotiation",
    9: "Under Contract",
    10: "Conditions / Follow-Up",
    11: "Sold",
    12: "Settlement / Post-Sale",
}

COMMON_ITEMS: dict[int, list[str]] = {
    1: [
        "Initial contact with vendor",
        "Property walk-through completed",
        "Comparable sales researched",
        "Appraisal report prepared",
    ],
    2: [
        "Appraisal presented to vendor",
        "Vendor expectations aligned",
        "Sale method discussed",
    ],
    3: [
        "Listing agreement signed",
        "Commission confirmed",
        "Vendor authority confirmed",
    ],
    4: [
        "LIM ordered",
        "Title search completed",
        "Compliance documents filed",
        "Agency file opened",
    ],
    5: [
        "Photographer booked",
        "Photos approved",
        "Copy written and approved",
        "Floor plan completed",
        "Signboard ordered",
    ],
    6: [
        "Listing live on Trade Me",
        "Listing live on realestate.co.nz",
        "Social media posted",
        "Email campaign sent",
    ],
    7: [
        "First open home completed",
        "Buyer feedback logged",
        "Follow-up calls made",
        "Second open home scheduled",
    ],
    8: [
        "Offer received",
        "Offer presented to vendor",
        "Negotiation completed",
    ],
    9: [
        "Sale and purchase agreement signed",
        "Deposit received",
        "Solicitors notified",
    ],
    10: [
        "Building inspection arranged",
        "Finance condition followed up",
        "All conditions satisfied",
    ],
    11: [
        "Sold sticker on signboard",
        "Vendor notified",
        "Settlement date confirmed",
    ],
    12: [
        "Keys handed over",
        "Settlement confirmed",
        "Post-sale follow-up with vendor",
        "Testimonial requested",
    ],
}

AUCTION_EXTRAS: dict[int, list[str]] = {
    5: [
        "Auction date set",
        "Auction terms confirmed",
        "Auction marketing scheduled",
    ],
    7: [
        "Pre-auction buyer follow-up",
        "Registered bidders confirmed",
    ],
    8: [
        "Auction conducted",
        "Passed-in negotiation if applicable",
    ],
}

DEADLINE_EXTRAS: dict[int, list[str]] = {
    5: [
        "Deadline date set and marketed",
    ],
    7: [
        "Buyer urgency follow-up",
        "Reminder cadence active",
    ],
    8: [
        "Deadline submissions reviewed",
        "Best offer selected",
    ],
}

PRICED_EXTRAS: dict[int, list[str]] = {
    5: [
        "Price set and approved by vendor",
    ],
    8: [
        "Price negotiation with buyer",
    ],
}

BY_NEGOTIATION_EXTRAS: dict[int, list[str]] = {
    5: [
        "Marketing copy reflects negotiation positioning",
    ],
    8: [
        "Negotiation strategy agreed with vendor",
    ],
}


def get_template_items(sale_method: str) -> dict[int, list[str]]:
    """Return phase -> list of item texts for the given sale method."""
    items = copy.deepcopy(COMMON_ITEMS)
    extras = {
        "auction": AUCTION_EXTRAS,
        "deadline": DEADLINE_EXTRAS,
        "priced": PRICED_EXTRAS,
        "by_negotiation": BY_NEGOTIATION_EXTRAS,
    }.get(sale_method, {})
    for phase, extra_items in extras.items():
        items[phase] = items.get(phase, []) + extra_items
    return items
