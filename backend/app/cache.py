import json
from pathlib import Path

import aiosqlite

from .models import AnalysisResult


class AnalysisCache:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    video_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.commit()

    async def get(self, video_id: str) -> AnalysisResult | None:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT payload FROM analyses WHERE video_id = ?",
                (video_id,),
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        result = AnalysisResult.model_validate(data)
        result.cached = True
        return result

    async def set(self, result: AnalysisResult) -> None:
        payload = result.model_dump(mode="json")
        payload["cached"] = False
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO analyses (video_id, payload)
                VALUES (?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    payload = excluded.payload,
                    created_at = CURRENT_TIMESTAMP
                """,
                (result.video_id, json.dumps(payload)),
            )
            await db.commit()
