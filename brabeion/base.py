from django.contrib.auth.models import User

from brabeion.models import BadgeAward
from brabeion.signals import badge_awarded



class BadgeAwarded(object):
    def __init__(self, level=None, badge_recipient=None):
        self.level = level
        self.badge_recipient = badge_recipient


class BadgeDetail(object):
    def __init__(self, name=None, description=None):
        self.name = name
        self.description = description


class Badge(object):
    async = False
    
    def __init__(self):
        assert not (self.multiple and len(self.levels) > 1)
        for i, level in enumerate(self.levels):
            if not isinstance(level, BadgeDetail):
                self.levels[i] = BadgeDetail(level)
    
    def possibly_award(self, **state):
        """
        Will see if the badge_recipient should be awarded a badge.  If this badge is
        asynchronous it just queues up the badge awarding.
        """
        assert "badge_recipient" in state
        if self.async:
            from brabeion.tasks import AsyncBadgeAward
            state = self.freeze(**state)
            AsyncBadgeAward.delay(self, state)
            return
        self.actually_possibly_award(**state)
    
    def actually_possibly_award(self, **state):
        """
        Does the actual work of possibly awarding a badge.
        """
        badge_recipient = state["badge_recipient"]
        force_timestamp = state.pop("force_timestamp", None)
        awarded = self.award(**state)
        if awarded is None:
            return
        if awarded.badge_recipient is not None:
            badge_recipient = awarded.badge_recipient
        if awarded.level is None:
            assert len(self.levels) == 1
            awarded.level = 1
        # awarded levels are 1 indexed, for conveineince
        awarded = awarded.level - 1
        assert awarded < len(self.levels)
        if (not self.multiple and
            BadgeAward.objects.filter(badge_recipient=badge_recipient, slug=self.slug, level=awarded)):
            return
        extra_kwargs = {}
        if force_timestamp is not None:
            extra_kwargs["awarded_at"] = force_timestamp
        badge = BadgeAward.objects.create(badge_recipient=badge_recipient, slug=self.slug,
            level=awarded, **extra_kwargs)
        badge_awarded.send(sender=self, badge_award=badge)
    
    def freeze(self, **state):
        return state


def send_badge_messages(badge_award, **kwargs):
    """
    If the Badge class defines a message, send it to the badge_recipient who was just
    awarded the badge.
    """
    # Send the message only if the badge recipient is a User
    if not isinstance(badge_recipient, User):
        return
    badge_recipient_message = getattr(badge_award.badge, "badge_recipient_message", None)
    if callable(badge_recipient_message):
        message = badge_recipient_message(badge_award)
    else:
        message = badge_recipient_message
    if message is not None:
        badge_award.badge_recipient.message_set.create(message=message)
badge_awarded.connect(send_badge_messages)
