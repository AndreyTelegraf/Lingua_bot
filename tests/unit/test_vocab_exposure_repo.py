import asyncio

from app.container import close_container, init_container, container
from modes.vocab.repo import VocabRepository


async def _get_item_id_by_lemma(conn, lemma: str) -> int:
    cursor = await conn.execute(
        "SELECT id FROM vocab_items WHERE lemma = ? ORDER BY id LIMIT 1",
        (lemma,),
    )
    row = await cursor.fetchone()
    assert row is not None, f"item_not_found:{lemma}"
    return int(row["id"])


def test_vocab_item_exposure_repo_smoke() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db
        repo = VocabRepository(conn)

        await repo.seed_demo_items_if_empty()

        item_id = await _get_item_id_by_lemma(conn, "casa")

        await conn.execute("DELETE FROM vocab_item_exposure WHERE item_id = ?", (item_id,))
        await conn.commit()

        await repo.mark_item_shown_global(item_id=item_id)
        await repo.mark_item_shown_global(item_id=item_id)
        await repo.mark_item_answered_global(item_id=item_id, is_correct=True)
        await repo.mark_item_answered_global(item_id=item_id, is_correct=False)

        row = await repo.get_item_exposure_stats(item_id=item_id)
        assert row is not None
        assert int(row["item_id"]) == item_id
        assert int(row["shown_count"]) == 2
        assert int(row["answered_count"]) == 2
        assert int(row["correct_count"]) == 1

        await close_container()

    asyncio.run(run())
