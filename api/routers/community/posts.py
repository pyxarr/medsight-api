# ruff: noqa: B008
import logging
from uuid import UUID as PythonUUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories.community_repository import CommunityRepository
from api.db.repositories.notification_repository import NotificationRepository
from api.db.session import get_db
from api.lib.auth import CurrentUser, get_current_user
from api.lib.storage import (
    build_community_media_path,
    delete_community_media,
    extract_storage_path_from_url,
    get_public_media_url,
    upload_community_media,
)
from api.models.community import CommunityPost
from api.models.user import User
from api.schemas.community import (
    AuthorInfo,
    FeedResponse,
    PostDetailResponse,
    PostResponse,
    ReactionCounts,
    ReplyResponse,
    SearchResponse,
    UserSearchResult,
)

LOGGER = logging.getLogger(__name__)

MAX_MEDIA_SIZE_BYTES = 5 * 1024 * 1024

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


def _serialise_user(user_dict: dict) -> UserSearchResult:
    """Convert one user dictionary into a user search result."""
    return UserSearchResult(
        id=user_dict["id"],
        display_name=user_dict["display_name"],
        username=user_dict["username"],
        avatar_url=user_dict["avatar_url"],
        role=user_dict["role"],
        is_verified=user_dict["is_verified"],
    )


@router.get("/feed", response_model=FeedResponse)
async def get_community_feed(
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> FeedResponse:
    """Return a paginated community feed of top-level posts ordered by creation time, newest first. Each post includes the author profile, reaction counts, and flags indicating whether the requesting user has liked, reposted, or bookmarked it. Use `limit` and `offset` for infinite scroll pagination."""
    repository = CommunityRepository()

    try:
        total_posts, posts = await repository.get_feed(
            database_session=database_session,
            requesting_user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load community feed for user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Feed could not be loaded. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return FeedResponse(
        total=total_posts,
        results=[_serialise_post(post) for post in posts],
    )


@router.get("/feed/following", response_model=FeedResponse)
async def get_following_feed(
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> FeedResponse:
    """Return a paginated feed of posts from users the authenticated user follows, ordered by creation time, newest first. Each post includes the author profile, reaction counts, and flags indicating whether the requesting user has liked, reposted, or bookmarked it. Use `limit` and `offset` for infinite scroll pagination."""
    repository = CommunityRepository()

    try:
        total_posts, posts = await repository.get_following_feed(
            database_session=database_session,
            requesting_user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load following feed for user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Following feed could not be loaded. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return FeedResponse(
        total=total_posts,
        results=[_serialise_post(post) for post in posts],
    )


async def _create_reply_notification_if_needed(
    database_session: AsyncSession,
    post_id: PythonUUID,
    actor_user_id: PythonUUID,
) -> None:
    """Create one reply notification when the actor replies to another user."""
    parent_author_query = select(CommunityPost.author_user_id).where(CommunityPost.id == post_id)
    parent_author_result = await database_session.execute(parent_author_query)
    parent_author_user_id = parent_author_result.scalar_one_or_none()

    if parent_author_user_id is None or parent_author_user_id == actor_user_id:
        return

    notification_repository = NotificationRepository()
    await notification_repository.create_notification(
        database_session=database_session,
        user_id=parent_author_user_id,
        type="reply",
        actor_user_id=actor_user_id,
        post_id=post_id,
    )


@router.get("/users/{user_id}/replies", response_model=FeedResponse)
async def get_user_replies(
    user_id: PythonUUID,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> FeedResponse:
    """Return a paginated feed of replies written by one user, newest first, using the standard community feed shape."""
    repository = CommunityRepository()

    try:
        total_posts, posts = await repository.get_user_replies(
            database_session=database_session,
            user_id=user_id,
            requesting_user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load user replies for user_id=%s requested_by=%s",
            user_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Replies could not be loaded. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return FeedResponse(
        total=total_posts,
        results=[_serialise_post(post) for post in posts],
    )


@router.get("/search", response_model=SearchResponse)
async def search_community(
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
    q: str = Query(default="", min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
) -> SearchResponse:
    """Search community content by keyword. Performs a case-insensitive substring match on post content for top-level posts, and on username and display name for users. Returns both result sets separately. Use `limit` to control the maximum number of results per set."""
    repository = CommunityRepository()

    try:
        results = await repository.search(
            database_session=database_session,
            query=q,
            requesting_user_id=current_user.id,
            limit=limit,
        )
    except Exception:
        LOGGER.exception(
            "Failed to search community for user_id=%s query=%s",
            current_user.id,
            q,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Search could not be completed. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return SearchResponse(
        posts=[_serialise_post(post) for post in results["posts"]],
        users=[_serialise_user(user) for user in results["users"]],
    )


@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_community_post(
    content: str = Form(...),
    file: UploadFile | None = File(None),
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> PostResponse:
    """Create a new top-level community post. The `content` field is required and supports plain text. An optional `file` field accepts any media type (images, videos, or other files) up to 5MB. The media is uploaded to Supabase Storage and a public URL is attached to the post. The post is attributed to the authenticated user."""
    repository = CommunityRepository()

    media_url = None
    if file is not None:
        file_bytes = await file.read()
        if len(file_bytes) > MAX_MEDIA_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Media file exceeds the 5MB size limit.",
            )

        storage_path = build_community_media_path(str(current_user.id), file.filename or "upload")
        try:
            upload_community_media(
                file_bytes=file_bytes,
                storage_path=storage_path,
                content_type=file.content_type or "application/octet-stream",
            )
        except RuntimeError:
            LOGGER.exception(
                "Failed to upload media for user_id=%s",
                current_user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Media could not be uploaded. Please try again or contact support if the problem persists.",
            )

        media_url = get_public_media_url(storage_path)

    try:
        post = await repository.create_post(
            database_session=database_session,
            author_user_id=current_user.id,
            content=content,
            media_url=media_url,
        )
    except Exception:
        LOGGER.exception(
            "Failed to create post for user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Post could not be created. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return PostResponse(
        id=post.id,
        content=post.content,
        media_url=post.media_url,
        view_count=post.view_count,
        created_at=post.created_at,
        author=_serialise_author(
            await _get_author(database_session, current_user.id)
        ),
        reaction_counts=ReactionCounts(
            like_count=0,
            reply_count=0,
            repost_count=0,
            bookmark_count=0,
            is_liked=False,
            is_reposted=False,
            is_bookmarked=False,
        ),
    )


@router.get("/posts/{post_id}", response_model=PostDetailResponse)
async def get_community_post(
    post_id: PythonUUID,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> PostDetailResponse:
    """Return a single post identified by its UUID, along with all direct replies. The post view count is incremented by one on each request. Replies are ordered by creation time, oldest first. Each post and reply includes the author profile, reaction counts, and flags for the requesting user interactions. Raises HTTP 404 if the post does not exist or has been soft-deleted."""
    repository = CommunityRepository()

    try:
        result = await repository.get_post_with_replies(
            database_session=database_session,
            post_id=post_id,
            requesting_user_id=current_user.id,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to load post_id=%s for user_id=%s",
            post_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Post could not be loaded. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return PostDetailResponse(
        id=result["post"].id,
        content=result["post"].content,
        media_url=result["post"].media_url,
        view_count=result["post"].view_count,
        created_at=result["post"].created_at,
        author=_serialise_author(result["author"]),
        reaction_counts=_serialise_reaction_counts({
            "like_count": result["like_count"],
            "reply_count": result["reply_count"],
            "repost_count": result["repost_count"],
            "bookmark_count": result["bookmark_count"],
            "is_liked": result["is_liked"],
            "is_reposted": result["is_reposted"],
            "is_bookmarked": result["is_bookmarked"],
        }),
        replies=[
            ReplyResponse(
                id=reply["post"].id,
                content=reply["post"].content,
                media_url=reply["post"].media_url,
                view_count=reply["post"].view_count,
                created_at=reply["post"].created_at,
                author=_serialise_author(reply["author"]),
                reaction_counts=_serialise_reaction_counts({
                    "like_count": reply["like_count"],
                    "reply_count": reply["reply_count"],
                    "repost_count": reply["repost_count"],
                    "bookmark_count": reply["bookmark_count"],
                    "is_liked": reply["is_liked"],
                    "is_reposted": reply["is_reposted"],
                    "is_bookmarked": reply["is_bookmarked"],
                }),
            )
            for reply in result["replies"]
        ],
    )


@router.post(
    "/posts/{post_id}/replies",
    response_model=ReplyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_community_reply(
    post_id: PythonUUID,
    content: str = Form(...),
    file: UploadFile | None = File(None),
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> ReplyResponse:
    """Create a reply to an existing post. The reply is attributed to the authenticated user and linked to the parent post. The `content` field is required. An optional `file` field accepts any media type (images, videos, or other files) up to 5MB. The media is uploaded to Supabase Storage and a public URL is attached to the reply. Raises HTTP 404 if the parent post does not exist or has been soft-deleted."""
    repository = CommunityRepository()

    media_url = None
    if file is not None:
        file_bytes = await file.read()
        if len(file_bytes) > MAX_MEDIA_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Media file exceeds the 5MB size limit.",
            )

        storage_path = build_community_media_path(str(current_user.id), file.filename or "upload")
        try:
            upload_community_media(
                file_bytes=file_bytes,
                storage_path=storage_path,
                content_type=file.content_type or "application/octet-stream",
            )
        except RuntimeError:
            LOGGER.exception(
                "Failed to upload media for user_id=%s",
                current_user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Media could not be uploaded. Please try again or contact support if the problem persists.",
            )

        media_url = get_public_media_url(storage_path)

    try:
        reply = await repository.create_reply(
            database_session=database_session,
            author_user_id=current_user.id,
            post_id=post_id,
            content=content,
            media_url=media_url,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to create reply to post_id=%s for user_id=%s",
            post_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Reply could not be created. Please try again or contact "
                "support if the problem persists."
            ),
        )

    try:
        await _create_reply_notification_if_needed(
            database_session=database_session,
            post_id=post_id,
            actor_user_id=current_user.id,
        )
    except Exception:
        LOGGER.exception(
            "Failed to create reply notification for post_id=%s from user_id=%s",
            post_id,
            current_user.id,
        )

    return ReplyResponse(
        id=reply.id,
        content=reply.content,
        media_url=reply.media_url,
        view_count=reply.view_count,
        created_at=reply.created_at,
        author=_serialise_author(
            await _get_author(database_session, current_user.id)
        ),
        reaction_counts=ReactionCounts(
            like_count=0,
            reply_count=0,
            repost_count=0,
            bookmark_count=0,
            is_liked=False,
            is_reposted=False,
            is_bookmarked=False,
        ),
    )


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_community_post(
    post_id: PythonUUID,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a post by setting its `deleted_at` timestamp. Only the post author can delete it. If the post has attached media, the media file is also deleted from Supabase Storage. Media deletion failure is logged but does not block the soft-delete. Raises HTTP 404 if the post does not exist. Raises HTTP 403 if the post does not belong to the authenticated user."""
    repository = CommunityRepository()

    post_query = repository._get_post_query(post_id)
    try:
        post_result = await database_session.execute(post_query)
        post = post_result.scalar_one_or_none()

        if post is None:
            raise HTTPException(status_code=404, detail="Post not found")

        if post.author_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorised to delete this post")

        if post.media_url is not None:
            storage_path = extract_storage_path_from_url(post.media_url)
            if storage_path is not None:
                try:
                    delete_community_media(storage_path)
                except RuntimeError:
                    LOGGER.exception(
                        "Failed to delete media for post_id=%s from Supabase Storage",
                        post_id,
                    )

        await repository.soft_delete_post(
            database_session=database_session,
            post_id=post_id,
            requesting_user_id=current_user.id,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to delete post_id=%s for user_id=%s",
            post_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Post could not be deleted. Please try again or contact "
                "support if the problem persists."
            ),
        )


async def _get_author(database_session: AsyncSession, user_id: PythonUUID):
    """Fetch the author record for serialisation after post creation."""
    user_query = select(User).where(User.id == user_id)
    user_result = await database_session.execute(user_query)
    return user_result.scalar_one()
