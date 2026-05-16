import asyncio, os
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://mindforge:mindforge@localhost:5432/mindforge')

async def main():
    from mindforge.infrastructure.config import load_settings
    from mindforge.infrastructure.db import make_async_engine
    from mindforge.infrastructure.persistence.artifact_repo import PostgresArtifactRepository
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    import uuid

    settings = load_settings()
    engine = make_async_engine(settings.database_url)
    sf = async_sessionmaker(engine, class_=AsyncSession)
    doc_id = uuid.UUID('3f3096e0-bcd3-4476-918d-8c0989404289')
    async with sf() as session:
        repo = PostgresArtifactRepository(session)
        artifact = await repo.load_latest(doc_id)
        if artifact and artifact.concept_map:
            cm = artifact.concept_map
            print(f'Concepts: {len(cm.concepts)}, Edges: {len(cm.edges)}')
            for e in cm.edges[:5]:
                print(f'  {e.source} -> {e.target} [{e.relation}]')
            if not cm.edges:
                print('NO EDGES in stored artifact')
                print(f'First 3 concept keys: {[c.key for c in list(cm.concepts)[:3]]}')
        else:
            print('No artifact or concept_map')

asyncio.run(main())
