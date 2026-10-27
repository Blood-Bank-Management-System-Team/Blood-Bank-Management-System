"""
ABO/Rh compatibility helpers for red blood cell transfusions.
"""

RECIPIENTS_BY_DONOR = {
    "O-": {"O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"},
    "O+": {"O+", "A+", "B+", "AB+"},
    "A-": {"A-", "A+", "AB-", "AB+"},
    "A+": {"A+", "AB+"},
    "B-": {"B-", "B+", "AB-", "AB+"},
    "B+": {"B+", "AB+"},
    "AB-": {"AB-", "AB+"},
    "AB+": {"AB+"},
}


def is_blood_compatible(donor_group, recipient_group):
    """
    Return whether donor red blood cells are compatible
    with the recipient's blood group.
    """
    compatible_recipients = RECIPIENTS_BY_DONOR.get(donor_group, set())
    return recipient_group in compatible_recipients