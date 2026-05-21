from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuthorInfo(BaseModel):
    """Author profile attached to a community post."""

    id: UUID
    display_name: str
    username: str
    avatar_url: str | None
    role: str
    is_verified: bool


class ReactionCounts(BaseModel):
    """Reaction totals and requesting-user flags for a post."""

    like_count: int
    reply_count: int
    repost_count: int
    bookmark_count: int
    is_liked: bool
    is_reposted: bool
    is_bookmarked: bool


class PostResponse(BaseModel):
    """One post with author details and reaction counts."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    media_url: str | None
    view_count: int
    created_at: datetime
    author: AuthorInfo
    reaction_counts: ReactionCounts


class ReplyResponse(PostResponse):
    """One reply — same shape as a post."""

    pass


class PostDetailResponse(BaseModel):
    """Single post view with all direct replies."""

    id: UUID
    content: str
    media_url: str | None
    view_count: int
    created_at: datetime
    author: AuthorInfo
    reaction_counts: ReactionCounts
    replies: list[ReplyResponse]


class FeedResponse(BaseModel):
    """Paginated feed listing."""

    total: int
    results: list[PostResponse]


class BookmarkResponse(BaseModel):
    """Paginated bookmarked posts listing."""

    total: int
    results: list[PostResponse]


class ReactionToggleResponse(BaseModel):
    """Updated reaction counts after toggling a reaction."""

    like_count: int
    repost_count: int
    bookmark_count: int
    is_liked: bool
    is_reposted: bool
    is_bookmarked: bool


class UserSearchResult(BaseModel):
    """One user result from community search."""

    id: UUID
    display_name: str
    username: str
    avatar_url: str | None
    role: str
    is_verified: bool


class SearchResponse(BaseModel):
    """Combined post and user search results."""

    posts: list[PostResponse]
    users: list[UserSearchResult]
