from dataclasses import dataclass
from typing import Literal

# I am too lazy to make enum and lucky enough for them to be unnecessary there
PrivacySettingsOptions = Literal[1, 2, 3]
PrivacySettingsCheckboxOptions = Literal[1, 3]
CommentPrivacySettingsOptions = Literal[0, 1, 2]


@dataclass(eq=False, slots=True)
class LocationData:
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


@dataclass(eq=False, slots=True)
class ProfileTheme:
    id: str  # theme_id
    title: str


@dataclass(eq=False, slots=True)
class ProfilePreferences:
    hide_profile_awards: int


@dataclass(eq=False, slots=True)
class MiniprofileMovie:
    video_webm: str | None  # video/webm
    video_mp4: str | None  # video/mp4


@dataclass(eq=False, slots=True)
class GoldenProfileDataEntry:
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
    available_themes: list[ProfileTheme]  # rgAvailableThemes
    golden_profile_data: list[GoldenProfileDataEntry]  # rgGoldenProfileData
    privacy: ProfilePrivacy  # Privacy


@dataclass(eq=False, slots=True)
class AvatarUploadImagesData:
    # 0: str
    medium: str
    full: str


@dataclass(eq=False, slots=True)
class AvatarUploadData:
    hash: str
    images: AvatarUploadImagesData
    message: str
