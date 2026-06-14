from scripts.seed_dev_data import seed_dev_data

from app.modules.config_center.service import get_task_config
from app.modules.prompt_registry.service import render_prompt
from app.modules.rag_service.schemas import RagSearchRequest
from app.modules.rag_service.service import search
from app.shared.database import SessionLocal


async def test_seed_dev_data_loads_initial_configs_and_prompt():
    await seed_dev_data()

    async with SessionLocal() as session:
        finance_config = await get_task_config(session, "finance_media", "dev", "generate_article")
        aigc_config = await get_task_config(session, "aigc_rtc", "dev", "voice_dialogue")

        version, rendered, variables_used = await render_prompt(
            session=session,
            project_id="finance_media",
            env="dev",
            prompt_key="finance.article.draft",
            version="v1",
            variables={
                "topic": "今日市场",
                "evidence": "新闻材料",
                "target_audience": "普通投资者",
            },
            trace_id="trace_seed_test",
        )
        base_version, base_prompt, _ = await render_prompt(
            session=session,
            project_id="aigc_rtc",
            env="dev",
            prompt_key="aigc.voice.persona.default",
            version="v1",
            variables={},
            trace_id="trace_seed_voice_base",
        )
        with_context_version, with_context_prompt, _ = await render_prompt(
            session=session,
            project_id="aigc_rtc",
            env="dev",
            prompt_key="aigc.voice.rag.with_context",
            version="v1",
            variables={"context": "[1] 7 天无理由退款"},
            trace_id="trace_seed_voice_context",
        )
        no_context_version, no_context_prompt, _ = await render_prompt(
            session=session,
            project_id="aigc_rtc",
            env="dev",
            prompt_key="aigc.voice.rag.no_context",
            version="v1",
            variables={},
            trace_id="trace_seed_voice_no_context",
        )
        rag_results = await search(
            session,
            RagSearchRequest(
                project_id="aigc_rtc",
                env="dev",
                kb_ids=["aigc_voice_kb"],
                query="退款 政策",
                top_k=3,
            ),
            "trace_seed_voice_rag",
        )

    assert finance_config.prompt_key == "finance.article.draft"
    assert aigc_config.prompt_key == "aigc.voice.persona.default"
    assert aigc_config.rag_enabled is True
    assert aigc_config.rag_policy_id == "aigc_voice_kb"
    assert version == "v1"
    assert "今日市场" in rendered
    assert variables_used == ["topic", "evidence", "target_audience"]
    assert base_version == "v1"
    assert "通用智能助手" in base_prompt
    assert with_context_version == "v1"
    assert "7 天无理由退款" in with_context_prompt
    assert no_context_version == "v1"
    assert "未在知识库中检索到" in no_context_prompt
    assert rag_results
    assert rag_results[0]["kb_id"] == "aigc_voice_kb"
