"""Group-scoped Famigo profile, discovery, and relationship operations."""

from datetime import datetime, timedelta
import re
import random

from sqlalchemy import or_

from database import (
    Achievement,
    CommunityEvent,
    Confession,
    ConfessionReaction,
    Connection,
    CurrentlyInto,
    DiscoveryHistory,
    Favorite,
    FamigoProfile,
    FamilyTreeNode,
    FamilyTreeRelation,
    GroupJoinHistory,
    MoodStatus,
    ProfileVisibility,
    RelationshipType,
    RelationshipVisibility,
    User,
    UserInterest,
    UserSettings,
)


PROFILE_FIELDS = {
    "name": "display_name",
    "city": "city",
    "country": "country",
    "pronouns": "pronouns",
    "age_range": "age_range",
    "bio": "bio",
    "intro": "introduction",
    "fun_fact": "fun_fact",
    "profession": "profession",
    "education": "education",
    "languages": "languages",
    "quote": "favorite_quote",
    "emoji": "favorite_emoji",
}

USER_PREFERENCES = {
    "discoverability": "allow_discoveries",
    "connection_requests": "allow_connections",
}


def ensure_user(session, user_id: int, username: str | None):
    user = session.query(User).filter(User.user_id == user_id).first()
    if user is None:
        user = User(user_id=user_id, username=username)
        session.add(user)
        session.flush()
    elif user.username != username:
        user.username = username
    return user


def get_profile(session, user_id: int, group_id: int):
    return session.query(FamigoProfile).filter(
        FamigoProfile.user_id == user_id,
        FamigoProfile.group_id == group_id,
    ).first()


def set_profile_field(session, user, group_id: int, field: str, value: str, first_name: str):
    attribute = PROFILE_FIELDS.get(field.lower())
    if attribute is None:
        raise ValueError("Choose a supported profile field.")
    if not value.strip() or len(value) > 250:
        raise ValueError("Profile values must be between 1 and 250 characters.")

    profile = get_profile(session, user.user_id, group_id)
    if profile is None:
        profile = FamigoProfile(
            user_id=user.user_id,
            group_id=group_id,
            display_name=first_name or "Member",
            visibility=ProfileVisibility.GROUP_ONLY,
        )
        session.add(profile)
    setattr(profile, attribute, value.strip())
    return profile


def set_profile_visibility(session, user_id: int, group_id: int, visibility: str):
    try:
        parsed_visibility = ProfileVisibility(visibility.lower())
    except ValueError as exc:
        raise ValueError("Choose public, group_only, or hidden.") from exc

    profile = get_profile(session, user_id, group_id)
    if profile is None:
        raise ValueError("Create your profile with /setprofile before changing its privacy.")
    profile.visibility = parsed_visibility
    return profile


def set_user_preference(session, user, preference: str, enabled: bool):
    attribute = USER_PREFERENCES.get(preference)
    if attribute is None:
        raise ValueError("That privacy preference is not supported.")
    settings = session.query(UserSettings).filter(
        UserSettings.user_id == user.user_id
    ).first()
    if settings is None:
        settings = UserSettings(user_id=user.user_id)
        session.add(settings)
    setattr(settings, attribute, enabled)
    return settings


def list_discoverable_profiles(session, group_id: int, exclude_user_id: int):
    profiles = session.query(FamigoProfile).filter(
        FamigoProfile.group_id == group_id,
        FamigoProfile.user_id != exclude_user_id,
        FamigoProfile.visibility != ProfileVisibility.HIDDEN,
    ).all()
    settings = {
        item.user_id: item
        for item in session.query(UserSettings).filter(
            UserSettings.user_id.in_([profile.user_id for profile in profiles])
        ).all()
    } if profiles else {}
    return [
        profile for profile in profiles
        if settings.get(profile.user_id) is None
        or settings[profile.user_id].allow_discoveries
    ]


def choose_random_profile(session, requester_id: int, group_id: int, profiles):
    if not profiles:
        return None

    history = session.query(DiscoveryHistory).filter(
        DiscoveryHistory.user_id == requester_id,
        DiscoveryHistory.group_id == group_id,
    ).first()
    candidates = profiles
    if history is not None and len(profiles) > 1:
        without_previous = [
            profile for profile in profiles
            if profile.user_id != history.last_discovered_user_id
        ]
        if without_previous:
            candidates = without_previous

    selected = random.choice(candidates)
    if history is None:
        history = DiscoveryHistory(
            user_id=requester_id,
            group_id=group_id,
            last_discovered_user_id=selected.user_id,
        )
        session.add(history)
    else:
        history.last_discovered_user_id = selected.user_id
    session.flush()
    return selected


def request_connection(
    session,
    requester_id: int,
    target_username: str | None,
    group_id: int,
    relationship: str,
    target_user_id: int | None = None,
):
    if target_user_id is not None:
        target = session.query(User).filter(User.user_id == target_user_id).first()
    else:
        username = (target_username or "").lstrip("@").strip()
        if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
            raise ValueError("Use a member's @username or reply to their group message.")
        target = session.query(User).filter(User.username.ilike(username)).first()
    if target is None or target.user_id == requester_id:
        raise ValueError("That member was not found in this group.")

    requester_profile = get_profile(session, requester_id, group_id)
    target_profile = get_profile(session, target.user_id, group_id)
    if (
        requester_profile is None
        or requester_profile.visibility == ProfileVisibility.HIDDEN
        or target_profile is None
        or target_profile.visibility == ProfileVisibility.HIDDEN
    ):
        raise ValueError("Both members need a visible profile in this group.")

    settings = {
        item.user_id: item.allow_connections
        for item in session.query(UserSettings).filter(
            UserSettings.user_id.in_([requester_id, target.user_id])
        ).all()
    }
    if settings.get(requester_id) is False or settings.get(target.user_id) is False:
        raise ValueError("One member is not accepting connection requests.")

    recent_requests = session.query(Connection).filter(
        Connection.user_id == requester_id,
        Connection.group_id == group_id,
        Connection.initiated_at >= datetime.utcnow() - timedelta(hours=1),
    ).count()
    if recent_requests >= 5:
        raise ValueError("You have sent the maximum number of connection requests for this hour.")

    try:
        relationship_type = RelationshipType(relationship.lower().replace(" ", "_"))
    except ValueError as exc:
        raise ValueError("That relationship type is not supported.") from exc

    existing = session.query(Connection).filter(
        Connection.group_id == group_id,
        Connection.status.in_(["pending", "accepted"]),
        (
            ((Connection.user_id == requester_id) & (Connection.connected_user_id == target.user_id))
            | ((Connection.user_id == target.user_id) & (Connection.connected_user_id == requester_id))
        ),
    ).first()
    if existing is not None:
        raise ValueError("A connection request or relationship already exists.")

    connection = Connection(
        user_id=requester_id,
        connected_user_id=target.user_id,
        group_id=group_id,
        relationship_type=relationship_type,
        visibility=RelationshipVisibility.PRIVATE,
        status="pending",
    )
    session.add(connection)
    session.flush()
    return connection, target


def respond_to_connection(session, connection_id: int, user_id: int, group_id: int, accept: bool):
    connection = session.query(Connection).filter(
        Connection.id == connection_id,
        Connection.group_id == group_id,
        Connection.connected_user_id == user_id,
        Connection.status == "pending",
    ).first()
    if connection is None:
        raise ValueError("This request is no longer available to you.")

    if accept:
        connection.status = "accepted"
        connection.accepted_at = datetime.utcnow()
    else:
        connection.status = "declined"
    return connection


def delete_group_profile(session, user_id: int, group_id: int):
    profile = get_profile(session, user_id, group_id)
    deleted = profile is not None

    for model in (
        UserInterest,
        Favorite,
        CurrentlyInto,
        MoodStatus,
        Achievement,
        GroupJoinHistory,
    ):
        deleted = bool(session.query(model).filter(
            model.user_id == user_id,
            model.group_id == group_id,
        ).delete(synchronize_session=False)) or deleted
    deleted = bool(session.query(Connection).filter(
        Connection.group_id == group_id,
        (
            (Connection.user_id == user_id)
            | (Connection.connected_user_id == user_id)
        ),
    ).delete(synchronize_session=False)) or deleted
    deleted = bool(session.query(ConfessionReaction).filter(
        ConfessionReaction.user_id == user_id,
        ConfessionReaction.confession_id.in_(
            session.query(Confession.id).filter(Confession.group_id == group_id)
        ),
    ).delete(synchronize_session=False)) or deleted
    confession_ids = [
        row[0] for row in session.query(Confession.id).filter(
            Confession.user_id == user_id,
            Confession.group_id == group_id,
        ).all()
    ]
    if confession_ids:
        deleted = bool(session.query(ConfessionReaction).filter(
            ConfessionReaction.confession_id.in_(confession_ids),
        ).delete(synchronize_session=False)) or deleted
        deleted = bool(session.query(Confession).filter(
            Confession.id.in_(confession_ids),
        ).delete(synchronize_session=False)) or deleted
    deleted = bool(session.query(CommunityEvent).filter(
        CommunityEvent.group_id == group_id,
        (
            (CommunityEvent.user_id == user_id)
            | (CommunityEvent.related_user_id == user_id)
        ),
    ).delete(synchronize_session=False)) or deleted
    deleted = bool(session.query(FamilyTreeRelation).filter(
        FamilyTreeRelation.group_id == group_id,
        or_(
            FamilyTreeRelation.user1_id == user_id,
            FamilyTreeRelation.user2_id == user_id,
        ),
    ).delete(synchronize_session=False)) or deleted
    profile_node_ids = [
        row[0] for row in session.query(FamilyTreeNode.id).filter(
            FamilyTreeNode.user_id == user_id,
            FamilyTreeNode.group_id == group_id,
        ).all()
    ]
    if profile_node_ids:
        deleted = bool(session.query(FamilyTreeNode).filter(
            FamilyTreeNode.group_id == group_id,
            FamilyTreeNode.parent_id.in_(profile_node_ids),
        ).update({FamilyTreeNode.parent_id: None}, synchronize_session=False)) or deleted
        deleted = bool(session.query(FamilyTreeNode).filter(
            FamilyTreeNode.id.in_(profile_node_ids),
        ).delete(synchronize_session=False)) or deleted
    deleted = bool(session.query(DiscoveryHistory).filter(
        DiscoveryHistory.group_id == group_id,
        or_(
            DiscoveryHistory.user_id == user_id,
            DiscoveryHistory.last_discovered_user_id == user_id,
        ),
    ).delete(synchronize_session=False)) or deleted
    if profile is not None:
        session.delete(profile)
    return deleted
