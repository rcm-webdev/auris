from fastapi import HTTPException, Request


async def get_current_session(request: Request) -> dict:
    token = request.cookies.get("better-auth.session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.name, u.email
            FROM "session" s
            JOIN "user" u ON u.id = s."userId"
            WHERE s.token = $1 AND s."expiresAt" > NOW()
            """,
            token,
        )
    if not row:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return dict(row)
