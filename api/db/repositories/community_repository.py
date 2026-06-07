from datetime import datetime, timezone
from uuid import UUID as PythonUUID

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.community import CommunityPost, CommunityReaction, Follow
from api.models.user import User


class CommunityRepository:
    """Handle persistence and retrieval for community posts, reactions, and follows."""

    def _get_post_query(self, post_id: str):
        """Return a select query for one post by identifier."""
        return select(CommunityPost).where(CommunityPost.id == post_id)

    async def create_post(
        self,
        database_session: AsyncSession,
        author_user_id: PythonUUID,
        content: str,
        media_url: str | None = None,
    ) -> CommunityPost:
        """Insert a new top-level community post and return the created record."""
        post = CommunityPost(
            author_user_id=author_user_id,
            content=content,
            media_url=media_url,
            parent_post_id=None,
        )
        database_session.add(post)
        await database_session.flush()
        await database_session.refresh(post)
        return post

    async def create_reply(
        self,
        database_session: AsyncSession,
        author_user_id: PythonUUID,
        post_id: PythonUUID,
        content: str,
        media_url: str | None = None,
    ) -> CommunityPost:
        """Insert a reply to an existing post. Raise HTTP 404 if the parent is missing or deleted."""
        parent_query = select(CommunityPost).where(
            CommunityPost.id == post_id,
            CommunityPost.deleted_at.is_(None),
        )
        parent_result = await database_session.execute(parent_query)
        parent_post = parent_result.scalar_one_or_none()

        if parent_post is None:
            raise HTTPException(status_code=404, detail="Post not found")

        reply = CommunityPost(
            author_user_id=author_user_id,
            content=content,
            media_url=media_url,
            parent_post_id=post_id,
        )
        database_session.add(reply)
        await database_session.flush()
        await database_session.refresh(reply)
        return reply

    async def get_feed(
        self,
        database_session: AsyncSession,
        requesting_user_id: PythonUUID,
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict]]:
        """Return paginated top-level posts with author details and reaction counts."""
        posts_query = select(CommunityPost).where(
            CommunityPost.parent_post_id.is_(None),
            CommunityPost.deleted_at.is_(None),
        )

        total_query = select(func.count()).select_from(CommunityPost).where(
            CommunityPost.parent_post_id.is_(None),
            CommunityPost.deleted_at.is_(None),
        )
        total_result = await database_session.execute(total_query)
        total_posts = total_result.scalar_one()

        posts_result = await database_session.execute(
            posts_query.order_by(CommunityPost.created_at.desc()).offset(offset).limit(limit)
        )
        posts = list(posts_result.scalars().all())

        if not posts:
            return total_posts, []

        return total_posts, await self._enrich_posts(
            database_session=database_session,
            posts=posts,
            requesting_user_id=requesting_user_id,
        )

    async def get_following_feed(
        self,
        database_session: AsyncSession,
        requesting_user_id: PythonUUID,
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict]]:
        """Return paginated posts from users the requesting user follows."""
        following_subquery = (
            select(Follow.following_id)
            .where(Follow.follower_id == requesting_user_id)
            .subquery()
        )

        posts_query = select(CommunityPost).where(
            CommunityPost.parent_post_id.is_(None),
            CommunityPost.deleted_at.is_(None),
            CommunityPost.author_user_id.in_(select(following_subquery.c.following_id)),
        )

        total_query = select(func.count()).select_from(CommunityPost).where(
            CommunityPost.parent_post_id.is_(None),
            CommunityPost.deleted_at.is_(None),
            CommunityPost.author_user_id.in_(select(following_subquery.c.following_id)),
        )
        total_result = await database_session.execute(total_query)
        total_posts = total_result.scalar_one()

        posts_result = await database_session.execute(
            posts_query.order_by(CommunityPost.created_at.desc()).offset(offset).limit(limit)
        )
        posts = list(posts_result.scalars().all())

        if not posts:
            return total_posts, []

        return total_posts, await self._enrich_posts(
            database_session=database_session,
            posts=posts,
            requesting_user_id=requesting_user_id,
        )

    async def get_post_with_replies(
        self,
        database_session: AsyncSession,
        post_id: PythonUUID,
        requesting_user_id: PythonUUID,
    ) -> dict:
        """Return a post with replies, increment view count, and raise HTTP 404 if missing or deleted."""
        post_query = select(CommunityPost).where(
            CommunityPost.id == post_id,
            CommunityPost.deleted_at.is_(None),
        )
        post_result = await database_session.execute(post_query)
        post = post_result.scalar_one_or_none()

        if post is None:
            raise HTTPException(status_code=404, detail="Post not found")

        post.view_count += 1
        await database_session.flush()

        replies_query = select(CommunityPost).where(
            CommunityPost.parent_post_id == post_id,
            CommunityPost.deleted_at.is_(None),
        ).order_by(CommunityPost.created_at.asc())
        replies_result = await database_session.execute(replies_query)
        replies = list(replies_result.scalars().all())

        enriched_replies = await self._enrich_posts(
            database_session=database_session,
            posts=replies,
            requesting_user_id=requesting_user_id,
        )

        enriched_post = (await self._enrich_posts(
            database_session=database_session,
            posts=[post],
            requesting_user_id=requesting_user_id,
        ))[0]
        enriched_post["replies"] = enriched_replies

        return enriched_post

    async def soft_delete_post(
        self,
        database_session: AsyncSession,
        post_id: PythonUUID,
        requesting_user_id: PythonUUID,
    ) -> CommunityPost:
        """Soft-delete a post. Raise HTTP 404 if missing, HTTP 403 if not owned by the requester."""
        post_query = select(CommunityPost).where(
            CommunityPost.id == post_id,
        )
        post_result = await database_session.execute(post_query)
        post = post_result.scalar_one_or_none()

        if post is None:
            raise HTTPException(status_code=404, detail="Post not found")

        if post.author_user_id != requesting_user_id:
            raise HTTPException(status_code=403, detail="Not authorised to delete this post")

        post.deleted_at = datetime.now(timezone.utc)
        await database_session.flush()
        await database_session.refresh(post)
        return post

    async def toggle_reaction(
        self,
        database_session: AsyncSession,
        post_id: PythonUUID,
        user_id: PythonUUID,
        reaction_type: str,
    ) -> dict:
        """Insert or delete a reaction and return updated reaction counts for the post."""
        existing_query = select(CommunityReaction).where(
            CommunityReaction.post_id == post_id,
            CommunityReaction.user_id == user_id,
            CommunityReaction.reaction_type == reaction_type,
        )
        existing_result = await database_session.execute(existing_query)
        existing_reaction = existing_result.scalar_one_or_none()

        if existing_reaction is not None:
            await database_session.delete(existing_reaction)
        else:
            reaction = CommunityReaction(
                post_id=post_id,
                user_id=user_id,
                reaction_type=reaction_type,
            )
            database_session.add(reaction)

        await database_session.flush()

        return await self._get_reaction_counts(
            database_session=database_session,
            post_id=post_id,
            requesting_user_id=user_id,
        )

    async def get_bookmarks(
        self,
        database_session: AsyncSession,
        user_id: PythonUUID,
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict]]:
        """Return paginated posts the user has bookmarked, ordered by reaction creation time."""
        bookmark_query = (
            select(CommunityPost)
            .join(
                CommunityReaction,
                and_(
                    CommunityReaction.post_id == CommunityPost.id,
                    CommunityReaction.user_id == user_id,
                    CommunityReaction.reaction_type == "bookmark",
                ),
            )
            .where(CommunityPost.deleted_at.is_(None))
        )

        total_query = (
            select(func.count())
            .select_from(CommunityPost)
            .join(
                CommunityReaction,
                and_(
                    CommunityReaction.post_id == CommunityPost.id,
                    CommunityReaction.user_id == user_id,
                    CommunityReaction.reaction_type == "bookmark",
                ),
            )
            .where(CommunityPost.deleted_at.is_(None))
        )
        total_result = await database_session.execute(total_query)
        total_bookmarks = total_result.scalar_one()

        bookmarks_result = await database_session.execute(
            bookmark_query.order_by(CommunityReaction.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        posts = list(bookmarks_result.scalars().all())

        if not posts:
            return total_bookmarks, []

        return total_bookmarks, await self._enrich_posts(
            database_session=database_session,
            posts=posts,
            requesting_user_id=user_id,
        )

    async def follow_user(
        self,
        database_session: AsyncSession,
        follower_id: PythonUUID,
        following_id: PythonUUID,
    ) -> None:
        """Insert a follow relationship, silently ignoring duplicate constraint violations."""
        follow = Follow(
            follower_id=follower_id,
            following_id=following_id,
        )
        database_session.add(follow)

        try:
            await database_session.flush()
        except IntegrityError:
            await database_session.rollback()

    async def unfollow_user(
        self,
        database_session: AsyncSession,
        follower_id: PythonUUID,
        following_id: PythonUUID,
    ) -> None:
        """Delete a follow relationship if it exists, otherwise do nothing."""
        follow_query = select(Follow).where(
            Follow.follower_id == follower_id,
            Follow.following_id == following_id,
        )
        follow_result = await database_session.execute(follow_query)
        follow = follow_result.scalar_one_or_none()

        if follow is not None:
            await database_session.delete(follow)
            await database_session.flush()

    async def search(
        self,
        database_session: AsyncSession,
        query: str,
        requesting_user_id: PythonUUID,
        limit: int,
    ) -> dict:
        """Search posts by content and users by username or display name, returning separate result sets."""
        normalised_query = f"%{query.lower()}%"

        posts_query = (
            select(CommunityPost)
            .where(
                CommunityPost.parent_post_id.is_(None),
                CommunityPost.deleted_at.is_(None),
                func.lower(CommunityPost.content).like(normalised_query),
            )
            .order_by(CommunityPost.created_at.desc())
            .limit(limit)
        )
        posts_result = await database_session.execute(posts_query)
        posts = list(posts_result.scalars().all())

        users_query = (
            select(User)
            .where(
                or_(
                    func.lower(User.username).like(normalised_query),
                    func.lower(User.display_name).like(normalised_query),
                )
            )
            .limit(limit)
        )
        users_result = await database_session.execute(users_query)
        users = list(users_result.scalars().all())

        enriched_posts = await self._enrich_posts(
            database_session=database_session,
            posts=posts,
            requesting_user_id=requesting_user_id,
        )

        user_results = [
            {
                "id": user.id,
                "display_name": user.display_name,
                "username": user.username,
                "avatar_url": user.avatar_url,
                "role": user.role,
                "is_verified": user.is_verified,
            }
            for user in users
        ]

        return {"posts": enriched_posts, "users": user_results}

    async def _enrich_posts(
        self,
        database_session: AsyncSession,
        posts: list[CommunityPost],
        requesting_user_id: PythonUUID,
    ) -> list[dict]:
        """Attach author details and reaction counts to a list of posts."""
        if not posts:
            return []

        post_ids = [post.id for post in posts]
        author_ids = list({post.author_user_id for post in posts})

        authors_query = select(User).where(User.id.in_(author_ids))
        authors_result = await database_session.execute(authors_query)
        authors_map = {user.id: user for user in authors_result.scalars().all()}

        reaction_counts = await self._get_bulk_reaction_counts(
            database_session=database_session,
            post_ids=post_ids,
            requesting_user_id=requesting_user_id,
        )

        enriched = []
        for post in posts:
            author = authors_map.get(post.author_user_id)
            counts = reaction_counts.get(post.id, {
                "like_count": 0,
                "reply_count": 0,
                "repost_count": 0,
                "bookmark_count": 0,
                "is_liked": False,
                "is_reposted": False,
                "is_bookmarked": False,
            })

            enriched.append({
                "post": post,
                "author": author,
                "like_count": counts["like_count"],
                "reply_count": counts["reply_count"],
                "repost_count": counts["repost_count"],
                "bookmark_count": counts["bookmark_count"],
                "is_liked": counts["is_liked"],
                "is_reposted": counts["is_reposted"],
                "is_bookmarked": counts["is_bookmarked"],
            })

        return enriched

    async def _get_reaction_counts(
        self,
        database_session: AsyncSession,
        post_id: PythonUUID,
        requesting_user_id: PythonUUID,
    ) -> dict:
        """Return reaction counts and user reaction flags for a single post."""
        reply_count_query = select(func.count()).select_from(CommunityPost).where(
            CommunityPost.parent_post_id == post_id,
            CommunityPost.deleted_at.is_(None),
        )
        reply_count_result = await database_session.execute(reply_count_query)
        reply_count = reply_count_result.scalar_one()

        like_count_query = select(func.count()).select_from(CommunityReaction).where(
            CommunityReaction.post_id == post_id,
            CommunityReaction.reaction_type == "like",
        )
        like_count_result = await database_session.execute(like_count_query)
        like_count = like_count_result.scalar_one()

        repost_count_query = select(func.count()).select_from(CommunityReaction).where(
            CommunityReaction.post_id == post_id,
            CommunityReaction.reaction_type == "repost",
        )
        repost_count_result = await database_session.execute(repost_count_query)
        repost_count = repost_count_result.scalar_one()

        bookmark_count_query = select(func.count()).select_from(CommunityReaction).where(
            CommunityReaction.post_id == post_id,
            CommunityReaction.reaction_type == "bookmark",
        )
        bookmark_count_result = await database_session.execute(bookmark_count_query)
        bookmark_count = bookmark_count_result.scalar_one()

        is_liked_query = select(func.count()).select_from(CommunityReaction).where(
            CommunityReaction.post_id == post_id,
            CommunityReaction.user_id == requesting_user_id,
            CommunityReaction.reaction_type == "like",
        )
        is_liked_result = await database_session.execute(is_liked_query)
        is_liked = is_liked_result.scalar_one() > 0

        is_reposted_query = select(func.count()).select_from(CommunityReaction).where(
            CommunityReaction.post_id == post_id,
            CommunityReaction.user_id == requesting_user_id,
            CommunityReaction.reaction_type == "repost",
        )
        is_reposted_result = await database_session.execute(is_reposted_query)
        is_reposted = is_reposted_result.scalar_one() > 0

        is_bookmarked_query = select(func.count()).select_from(CommunityReaction).where(
            CommunityReaction.post_id == post_id,
            CommunityReaction.user_id == requesting_user_id,
            CommunityReaction.reaction_type == "bookmark",
        )
        is_bookmarked_result = await database_session.execute(is_bookmarked_query)
        is_bookmarked = is_bookmarked_result.scalar_one() > 0

        return {
            "like_count": like_count,
            "reply_count": reply_count,
            "repost_count": repost_count,
            "bookmark_count": bookmark_count,
            "is_liked": is_liked,
            "is_reposted": is_reposted,
            "is_bookmarked": is_bookmarked,
        }

    async def _get_bulk_reaction_counts(
        self,
        database_session: AsyncSession,
        post_ids: list[PythonUUID],
        requesting_user_id: PythonUUID,
    ) -> dict[PythonUUID, dict]:
        """Return reaction counts and user flags for multiple posts in a single query."""
        reaction_query = select(
            CommunityReaction.post_id,
            CommunityReaction.reaction_type,
            CommunityReaction.user_id == requesting_user_id,
        ).where(CommunityReaction.post_id.in_(post_ids))
        reaction_result = await database_session.execute(reaction_query)
        reaction_rows = reaction_result.all()

        reply_count_query = (
            select(CommunityPost.parent_post_id, func.count())
            .where(
                CommunityPost.parent_post_id.in_(post_ids),
                CommunityPost.deleted_at.is_(None),
            )
            .group_by(CommunityPost.parent_post_id)
        )
        reply_count_result = await database_session.execute(reply_count_query)
        reply_counts = dict(reply_count_result.all())

        counts_map: dict[PythonUUID, dict] = {}
        for post_id in post_ids:
            counts_map[post_id] = {
                "like_count": 0,
                "reply_count": reply_counts.get(post_id, 0),
                "repost_count": 0,
                "bookmark_count": 0,
                "is_liked": False,
                "is_reposted": False,
                "is_bookmarked": False,
            }

        for post_id, reaction_type, is_requesting_user in reaction_rows:
            if reaction_type == "like":
                counts_map[post_id]["like_count"] += 1
                if is_requesting_user:
                    counts_map[post_id]["is_liked"] = True
            elif reaction_type == "repost":
                counts_map[post_id]["repost_count"] += 1
                if is_requesting_user:
                    counts_map[post_id]["is_reposted"] = True
            elif reaction_type == "bookmark":
                counts_map[post_id]["bookmark_count"] += 1
                if is_requesting_user:
                    counts_map[post_id]["is_bookmarked"] = True

        return counts_map
