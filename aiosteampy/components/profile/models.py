from dataclasses import dataclass
from datetime import datetime
from typing import Literal, NamedTuple

# I am too lazy to make enum and lucky enough for them to be unnecessary there
PrivacySettingsOptions = Literal[1, 2, 3]
PrivacySettingsCheckboxOptions = Literal[1, 3]
CommentPrivacySettingsOptions = Literal[0, 1, 2]


class LocationData(NamedTuple):
    city: str  # locCity
    city_code: int  # locCityCode
    country: str  # locCountry
    country_code: str  # locCountryCode
    state: str  # locState
    state_code: str  # locStateCode


@dataclass(eq=False, slots=True)
class ProfilePrivacySettings:
    """
    Privacy levels:
        * 1 - private
        * 2 - friends only
        * 3 - public
    """

    friends_list: PrivacySettingsOptions  # PrivacyFriendsList
    inventory: PrivacySettingsOptions  # PrivacyInventory
    inventory_gifts: PrivacySettingsCheckboxOptions  # PrivacyInventoryGifts
    owned_games: PrivacySettingsOptions  # PrivacyOwnedGames
    playtime: PrivacySettingsCheckboxOptions  # PrivacyPlaytime
    profile: PrivacySettingsOptions  # PrivacyProfile


@dataclass(eq=False, slots=True)
class ProfilePrivacy:
    """
    Comment permission levels:
        * 2 - private
        * 0 - friends only
        * 1 - public
    """

    settings: ProfilePrivacySettings  # PrivacySettings
    comment_permission: CommentPrivacySettingsOptions  # eCommentPermission


class ProfileTheme(NamedTuple):
    id: str  # theme_id
    title: str


class ProfilePreferences(NamedTuple):
    hide_profile_awards: int


class MiniprofileMovie(NamedTuple):
    video_webm: str | None  # video/webm
    video_mp4: str | None  # video/mp4


class GoldenProfileDataEntry(NamedTuple):
    appid: int
    css_url: str
    frame_url: str | None
    miniprofile_background: str | None
    miniprofile_movie: MiniprofileMovie | None


@dataclass(eq=False, slots=True)
class ProfileData:
    persona_name: str  # strPersonaName
    custom_url: str | None  # strCustomURL
    real_name: str  # strRealName
    summary: str  # strSummary
    avatar_hash: str  # strAvatarHash
    persona_name_banned_until: str  # rtPersonaNameBannedUntil
    profile_summary_banned_until: str  # rtProfileSummaryBannedUntil
    avatar_banned_until: str  # rtAvatarBannedUntil
    location_data: LocationData  # LocationData
    active_theme: ProfileTheme  # ActiveTheme
    profile_preferences: ProfilePreferences  # ProfilePreferences
    available_themes: tuple[ProfileTheme, ...]  # rgAvailableThemes
    golden_profile_data: tuple[GoldenProfileDataEntry, ...]  # rgGoldenProfileData
    privacy: ProfilePrivacy  # Privacy


class AvatarUploadImagesData(NamedTuple):
    # 0: str
    medium: str
    full: str


class AvatarUploadData(NamedTuple):
    hash: str
    images: AvatarUploadImagesData
    message: str


class ProfileAliasHistoryEntry(NamedTuple):
    new_name: str
    time_changed: datetime


class MiniProfileBadge(NamedTuple):
    description: str
    icon: str
    level: int
    name: str
    xp: str


class MiniProfileData(NamedTuple):
    avatar: str
    favorite_badge: MiniProfileBadge | None
    level: int
    level_class: str
    persona_name: str
