import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories.community_repository import CommunityRepository
from api.db.session import get_db
from api.lib.auth import CurrentUser, get_current_user
from api.schemas.community import (
    AuthorInfo,
    BookmarkResponse,
    PostResponse,
    ReactionCounts,
    ReactionToggleResponse,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter()


def _serialise_author(author) -> AuthorInfo:
    """Convert one user record into an author info response."""
    return AuthorInfo(
        id=author.id,
        display_name=author.display_name,
        username=author.username,
        avatar_url=author.avatar_url,
        role=author.role,
        is_verified=author.is_verified,
    )


def _serialise_reaction_counts(counts_dict: dict) -> ReactionCounts:
    """Convert one reaction counts dictionary into a reaction counts response."""
    return ReactionCounts(
        like_count=counts_dict["like_count"],
        reply_count=counts_dict["reply_count"],
        repost_count=counts_dict["repost_count"],
        bookmark_count=counts_dict["bookmark_count"],
        is_liked=counts_dict["is_liked"],
        is_reposted=counts_dict["is_reposted"],
        is_bookmarked=counts_dict["is_bookmarked"],
    )


def _serialise_post(enriched_post_dict: dict) -> PostResponse:
    """Convert one enriched post dictionary into a post response."""
    return PostResponse(
        id=enriched_post_dict["post"].id,
        content=enriched_post_dict["post"].content,
        media_url=enriched_post_dict["post"].media_url,
        view_count=enriched_post_dict["post"].view_count,
        created_at=enriched_post_dict["post"].created_at,
        author=_serialise_author(enriched_post_dict["author"]),
        reaction_counts=_serialise_reaction_counts({
            "like_count": enriched_post_dict["like_count"],
            "reply_count": enriched_post_dict["reply_count"],
            "repost_count": enriched_post_dict["repost_count"],
            "bookmark_count": enriched_post_dict["bookmark_count"],
            "is_liked": enriched_post_dict["is_liked"],
            "is_reposted": enriched_post_dict["is_reposted"],
            "is_bookmarked": enriched_post_dict["is_bookmarked"],
        }),
    )


async def _handle_toggle_reaction(
    post_id: str,
    reaction_type: str,
    current_user: CurrentUser,
    database_session: AsyncSession,
) -> ReactionToggleResponse:
    """Toggle a reaction and return the updated counts."""
    repository = CommunityRepository()

    try:
        return await repository.toggle_reaction(
            database_session=database_session,
            post_id=post_id,
            user_id=current_user.id,
            reaction_type=reaction_type,
        )
    except Exception:
        LOGGER.exception(
            "Failed to toggle %s reaction on post_id=%s for user_id=%s",
            reaction_type,
            post_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Reaction could not be updated. Please try again or contact "
                "support if the problem persists."
            ),
        )


@router.post("/posts/{post_id}/like", response_model=ReactionToggleResponse)
async def toggle_like(
    post_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> ReactionToggleResponse:
    """Toggle a like reaction on a post. If the authenticated user has already liked the post, the like is removed. If not, a like is added. Returns the updated reaction counts for the post."""
    return ReactionToggleResponse(
        **await _handle_toggle_reaction(
            post_id=post_id,
            reaction_type="like",
            current_user=current_user,
            database_session=database_session,
        )
    )


@router.post("/posts/{post_id}/repost", response_model=ReactionToggleResponse)
async def toggle_repost(
    post_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> ReactionToggleResponse:
    """Toggle a repost reaction on a post. If the authenticated user has already reposted the post, the repost is removed. If not, a repost is added. Returns the updated reaction counts for the post."""
    return ReactionToggleResponse(
        **await _handle_toggle_reaction(
            post_id=post_id,
            reaction_type="repost",
            current_user=current_user,
            database_session=database_session,
        )
    )


@router.post("/posts/{post_id}/bookmark", response_model=ReactionToggleResponse)
async def toggle_bookmark(
    post_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> ReactionToggleResponse:
    """Toggle a bookmark reaction on a post. If the authenticated user has already bookmarked the post, the bookmark is removed. If not, a bookmark is added. Returns the updated reaction counts for the post."""
    return ReactionToggleResponse(
        **await _handle_toggle_reaction(
            post_id=post_id,
            reaction_type="bookmark",
            current_user=current_user,
            database_session=database_session,
        )
    )


@router.get("/bookmarks", response_model=BookmarkResponse)
async def get_user_bookmarks(
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> BookmarkResponse:
    """Return a paginated list of posts the authenticated user has bookmarked, ordered by the time the bookmark was created, newest first. Each post includes the author profile, reaction counts, and interaction flags. Use `limit` and `offset` for infinite scroll pagination."""
    repository = CommunityRepository()

    try:
        total_bookmarks, bookmarks = await repository.get_bookmarks(
            database_session=database_session,
            user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load bookmarks for user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Bookmarks could not be loaded. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return BookmarkResponse(
        total=total_bookmarks,
        results=[_serialise_post(bookmark) for bookmark in bookmarks],
    )
