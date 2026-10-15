"""Durable log storage boundary. SQL chunks are the initial implementation."""

from sqlalchemy import select

from .models import JobLogMetadata


class SQLLogStore:
    def append(self, db, owner, stream, sequence, text):
        exists = db.scalar(
            select(JobLogMetadata).where(
                JobLogMetadata.owner_id == owner,
                JobLogMetadata.stream == stream,
                JobLogMetadata.sequence == sequence,
            )
        )
        if not exists:
            db.add(JobLogMetadata(owner_id=owner, stream=stream, sequence=sequence, text=text))

    def read(self, db, owner, stream, after=-1, limit=200):
        return db.scalars(
            select(JobLogMetadata)
            .where(
                JobLogMetadata.owner_id == owner,
                JobLogMetadata.stream == stream,
                JobLogMetadata.sequence > after,
            )
            .order_by(JobLogMetadata.sequence)
            .limit(limit)
        ).all()


logs = SQLLogStore()
