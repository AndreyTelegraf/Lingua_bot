import asyncio

from app.container import close_container, init_container, container
from modes.vocab.renderer import VocabRenderer
from modes.vocab.repo import VocabRepository


def test_renderer_returns_exactly_six_choices_for_demo_items() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db

        repo = VocabRepository(conn)
        await repo.seed_demo_items_if_empty()

        renderer = VocabRenderer(conn)

        for lemma in ("casa", "comer", "rápido"):
            cur = await conn.execute(
                "SELECT id FROM vocab_items WHERE lemma = ? ORDER BY id ASC LIMIT 1",
                (lemma,),
            )
            row = await cur.fetchone()
            assert row is not None
            item_id = int(row["id"])

            payload = await renderer.build_question_payload(item_id=item_id)
            choices = payload["choices"]

            assert isinstance(choices, list)
            assert len(choices) == 6

            position_indexes = [int(c["position_index"]) for c in choices]
            assert position_indexes == [1, 2, 3, 4, 5, 6]

            correct_n = 0
            for choice in choices:
                cur2 = await conn.execute(
                    "SELECT is_correct FROM vocab_choices WHERE id = ?",
                    (int(choice["choice_id"]),),
                )
                row2 = await cur2.fetchone()
                assert row2 is not None
                correct_n += int(row2["is_correct"])

            assert correct_n == 1

        await close_container()

    asyncio.run(run())
