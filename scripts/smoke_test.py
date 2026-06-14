import asyncio

from app.modules.config_center.service import get_task_config
from app.modules.prompt_registry.service import render_prompt
from app.modules.rag_service.schemas import RagSearchRequest
from app.modules.rag_service.service import search
from app.shared.database import SessionLocal
from scripts.seed_dev_data import seed_dev_data


async def smoke_test() -> None:
    await seed_dev_data()
    async with SessionLocal() as session:
        config = await get_task_config(session, "aigc_rtc", "dev", "voice_dialogue")
        version, rendered, _ = await render_prompt(
            session=session,
            project_id="aigc_rtc",
            env="dev",
            prompt_key="aigc.voice.rag.with_context",
            version="v1",
            variables={"context": "[1] 退款政策"},
            trace_id="trace_smoke_prompt",
        )
        results = await search(
            session,
            RagSearchRequest(
                project_id="aigc_rtc",
                env="dev",
                kb_ids=["aigc_voice_kb"],
                query="\u9000\u6b3e \u653f\u7b56",
                top_k=3,
            ),
            "trace_smoke_rag",
        )

    print(
        "Smoke test completed:",
        {
            "task": f"{config.project_id}/{config.env}/{config.task_type}",
            "model_policy_id": config.model_policy_id,
            "rag_policy_id": config.rag_policy_id,
            "prompt_version": version,
            "prompt_contains_context": "退款政策" in rendered,
            "rag_result_count": len(results),
            "first_rag_title": results[0]["title"] if results else None,
        },
    )


def main() -> None:
    asyncio.run(smoke_test())


if __name__ == "__main__":
    main()
