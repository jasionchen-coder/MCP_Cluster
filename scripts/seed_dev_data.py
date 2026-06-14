import asyncio
import json

from sqlalchemy import select

from app.modules.config_center.schemas import TaskConfigUpsert
from app.modules.config_center.service import upsert_task_config
from app.modules.llm_gateway.models import (
    LLMModelEndpoint,
    LLMModelPolicy,
    LLMModelProvider,
)
from app.shared.config import get_settings
from app.modules.prompt_registry.models import PromptTemplate, PromptVersion
from app.modules.prompt_registry.schemas import PromptCreate, PromptVersionCreate
from app.modules.prompt_registry.service import (
    create_prompt,
    create_prompt_version,
    publish_prompt_version,
)
from app.modules.rag_service.models import KnowledgeBase, RagDocument
from app.modules.rag_service.schemas import DocumentCreate, KnowledgeBaseCreate
from app.modules.rag_service.service import backfill_embeddings, create_knowledge_base, ingest_document
from app.shared.database import SessionLocal, init_db
from app.shared.errors import APIError


async def _seed_llm_gateway() -> None:
    settings = get_settings()

    async with SessionLocal() as session:
        existing = (
            await session.execute(
                select(LLMModelProvider).where(LLMModelProvider.provider_name == "ark")
            )
        ).scalar_one_or_none()

        if existing is None:
            provider = LLMModelProvider(
                provider_name="ark",
                base_url=settings.ark_base_url,
                api_key_env="ARK_API_KEY",
                enabled=True,
            )
            session.add(provider)
            await session.flush()
            provider_id = provider.id
        else:
            provider_id = existing.id

        async def _upsert_endpoint(model_name: str, endpoint_id: str) -> int:
            existing_ep = (
                await session.execute(
                    select(LLMModelEndpoint).where(
                        LLMModelEndpoint.provider_id == provider_id,
                        LLMModelEndpoint.endpoint_id == endpoint_id,
                    )
                )
            ).scalar_one_or_none()
            if existing_ep is not None:
                return existing_ep.id
            ep = LLMModelEndpoint(
                provider_id=provider_id,
                model_name=model_name,
                endpoint_id=endpoint_id,
                supports_stream=True,
                supports_json=True,
                max_context_tokens=128000,
                enabled=True,
            )
            session.add(ep)
            await session.flush()
            return ep.id

        finance_ep_id = await _upsert_endpoint(
            f"Ark {settings.ark_default_model}", settings.ark_default_model
        )
        topic_ep_id = await _upsert_endpoint(
            f"Ark {settings.ark_topic_model}", settings.ark_topic_model
        )
        image_ep_id = await _upsert_endpoint(
            f"Image {settings.ark_image_model}", settings.ark_image_model
        )
        voice_ep_id = await _upsert_endpoint(
            f"Ark {settings.ark_default_model}", settings.ark_default_model
        )

        policies = [
            ("finance_high_quality", "finance_media", "generate_article", finance_ep_id),
            ("finance_json_stable", "finance_media", "generate_article", finance_ep_id),
            ("finance_article_writer", "finance_media", "article_writer", finance_ep_id),
            ("finance_article_reviser", "finance_media", "article_reviser", finance_ep_id),
            ("finance_xhs_copy_writer", "finance_media", "xhs_copy_writer", finance_ep_id),
            ("finance_image_prompt_json", "finance_media", "image_prompt_extractor", finance_ep_id),
            ("finance_topic_gen", "finance_media", "generate_topic", topic_ep_id),
            ("finance_image_gen", "finance_media", "generate_image", image_ep_id),
            ("voice_low_latency", "aigc_rtc", "voice_dialogue", voice_ep_id),
        ]
        for policy_id, project_id, task_type, ep_id in policies:
            existing_pol = (
                await session.execute(
                    select(LLMModelPolicy)
                    .where(
                        LLMModelPolicy.policy_id == policy_id,
                        LLMModelPolicy.project_id == project_id,
                        LLMModelPolicy.env == "dev",
                        LLMModelPolicy.task_type == task_type,
                    )
                    .order_by(LLMModelPolicy.id)
                )
            ).scalars().first()
            if existing_pol is not None:
                continue
            session.add(
                LLMModelPolicy(
                    policy_id=policy_id,
                    project_id=project_id,
                    env="dev",
                    task_type=task_type,
                    primary_model_id=ep_id,
                    fallback_model_id=None,
                    timeout_ms=30000,
                    max_retries=0,
                    default_temperature=0.3,
                    default_max_tokens=2048,
                    enabled=True,
                )
            )

        await session.commit()


async def _ensure_prompt(
    prompt: PromptCreate,
    version: PromptVersionCreate,
) -> None:
    async with SessionLocal() as session:
        existing_prompt = (
            await session.execute(
                select(PromptTemplate).where(PromptTemplate.prompt_key == prompt.prompt_key)
            )
        ).scalar_one_or_none()
        if existing_prompt is None:
            await create_prompt(session, prompt)
        existing_version = (
            await session.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_key == prompt.prompt_key,
                    PromptVersion.version == version.version,
                )
            )
        ).scalar_one_or_none()
        if existing_version is None:
            await create_prompt_version(session, prompt.prompt_key, version)
        else:
            existing_version.content = version.content
            existing_version.variables_schema = version.variables_schema
            existing_version.status = version.status
            await session.commit()
        try:
            await publish_prompt_version(session, prompt.prompt_key, version.version)
        except APIError:
            raise


async def _ensure_knowledge_base(payload: KnowledgeBaseCreate) -> None:
    async with SessionLocal() as session:
        existing = (
            await session.execute(
                select(KnowledgeBase).where(
                    KnowledgeBase.env == payload.env,
                    KnowledgeBase.kb_id == payload.kb_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            await create_knowledge_base(session, payload)


async def _ensure_document(payload: DocumentCreate) -> None:
    async with SessionLocal() as session:
        existing = (
            await session.execute(
                select(RagDocument).where(
                    RagDocument.project_id == payload.project_id,
                    RagDocument.env == payload.env,
                    RagDocument.kb_id == payload.kb_id,
                    RagDocument.title == payload.title,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            await ingest_document(session, payload)


async def seed_dev_data() -> None:
    await init_db()
    await _seed_llm_gateway()
    async with SessionLocal() as session:
        await upsert_task_config(
            session,
            "finance_media",
            "dev",
            "generate_article",
            TaskConfigUpsert(
                prompt_key="finance.article.draft",
                prompt_version="v1",
                model_policy_id="finance_high_quality",
                rag_enabled=True,
                rag_policy_id="finance_news_rag",
                enabled=True,
            ),
        )
        await upsert_task_config(
            session,
            "finance_media",
            "dev",
            "generate_topic",
            TaskConfigUpsert(
                prompt_key="finance.topic.generator",
                prompt_version="v1",
                model_policy_id="finance_topic_gen",
                rag_enabled=False,
                rag_policy_id=None,
                enabled=True,
            ),
        )
        await upsert_task_config(
            session,
            "finance_media",
            "dev",
            "article_writer",
            TaskConfigUpsert(
                prompt_key="article_writer",
                prompt_version="v1",
                model_policy_id="finance_article_writer",
                rag_enabled=True,
                rag_policy_id="finance_news_rag",
                enabled=True,
            ),
        )
        await upsert_task_config(
            session,
            "finance_media",
            "dev",
            "article_reviser",
            TaskConfigUpsert(
                prompt_key="article_reviser",
                prompt_version="v1",
                model_policy_id="finance_article_reviser",
                rag_enabled=False,
                rag_policy_id=None,
                enabled=True,
            ),
        )
        await upsert_task_config(
            session,
            "finance_media",
            "dev",
            "xhs_copy_writer",
            TaskConfigUpsert(
                prompt_key="xhs_copy_writer",
                prompt_version="v1",
                model_policy_id="finance_xhs_copy_writer",
                rag_enabled=False,
                rag_policy_id=None,
                enabled=True,
            ),
        )
        await upsert_task_config(
            session,
            "finance_media",
            "dev",
            "image_prompt_extractor",
            TaskConfigUpsert(
                prompt_key="image_prompt_extractor",
                prompt_version="v1",
                model_policy_id="finance_image_prompt_json",
                rag_enabled=False,
                rag_policy_id=None,
                enabled=True,
            ),
        )
        await upsert_task_config(
            session,
            "aigc_rtc",
            "dev",
            "voice_dialogue",
            TaskConfigUpsert(
                prompt_key="aigc.voice.persona.default",
                prompt_version="v1",
                model_policy_id="voice_low_latency",
                rag_enabled=True,
                rag_policy_id="aigc_voice_kb",
                enabled=True,
            ),
        )
        await upsert_task_config(
            session,
            "finance_media",
            "dev",
            "generate_image",
            TaskConfigUpsert(
                prompt_key="finance.image.prompt",
                prompt_version="v1",
                model_policy_id="finance_image_gen",
                rag_enabled=False,
                rag_policy_id=None,
                enabled=True,
            ),
        )

    await _ensure_prompt(
        PromptCreate(
            project_id="finance_media",
            prompt_key="topic_generator",
            name="选题生成 Prompt",
            description="根据运营背景生成候选选题",
            default_version="v1",
        ),
        PromptVersionCreate(
            version="v1",
            content=json.dumps({
                "system": "你是一位资深的金融自媒体主编，擅长基于当日热点产出兼具流量与专业度的选题。如果有联网搜索工具可用，请先调用它获取最新市场动态，以确保选题具有时效性。最终输出 5 个备选选题，每个不超过 30 字，避免标题党，但要具备话题性。",
                "user_template": "【运营背景备注】\n{{context}}\n\n请判断是否需要联网搜索最新金融热点，然后以 JSON 对象格式输出 5 个备选选题，例如：\n{{\"topics\": [\"选题 A\", \"选题 B\", \"选题 C\", \"选题 D\", \"选题 E\"]}}",
            }, ensure_ascii=False),
            variables_schema={
                "type": "object",
                "properties": {"context": {"type": "string"}},
                "required": ["context"],
            },
            status="published",
        ),
    )
    await _ensure_prompt(
        PromptCreate(
            project_id="finance_media",
            prompt_key="article_writer",
            name="文章生成 Prompt",
            description="根据选题和资讯生成金融长文",
            default_version="v1",
        ),
        PromptVersionCreate(
            version="v1",
            content=json.dumps({
                "system": "你是金融领域的专业撰稿人，写作风格沉稳、信息密度高，约 1200 字一篇。需包含：核心观点、数据支撑、风险提示、对普通投资者的建议。若提供了最新资讯，须结合其中的时效性数据和事件撰写，体现文章的时效性。",
                "user_template": "选题：{{selected_topic}}\n背景：{{context}}\n\n【最新相关资讯】\n{{search_results}}\n\n请直接输出正文，不要包含标题。",
            }, ensure_ascii=False),
            variables_schema={
                "type": "object",
                "properties": {
                    "selected_topic": {"type": "string"},
                    "context": {"type": "string"},
                    "search_results": {"type": "string"},
                },
                "required": ["selected_topic", "context"],
            },
            status="published",
        ),
    )
    await _ensure_prompt(
        PromptCreate(
            project_id="finance_media",
            prompt_key="article_reviser",
            name="文章修订 Prompt",
            description="根据修改意见重写文章",
            default_version="v1",
        ),
        PromptVersionCreate(
            version="v1",
            content=json.dumps({
                "system": "你是一位严苛的金融主编，根据修改意见对原文进行重写，需保留原有数据支撑。",
                "user_template": "原文：\n{{draft_article}}\n\n修改意见：\n{{human_feedback}}\n\n请输出修改后的全文。",
            }, ensure_ascii=False),
            variables_schema={
                "type": "object",
                "properties": {
                    "draft_article": {"type": "string"},
                    "human_feedback": {"type": "string"},
                },
                "required": ["draft_article", "human_feedback"],
            },
            status="published",
        ),
    )
    await _ensure_prompt(
        PromptCreate(
            project_id="finance_media",
            prompt_key="image_prompt_extractor",
            name="图片提示词提取 Prompt",
            description="从长文中提取配图所需的观点文案",
            default_version="v1",
        ),
        PromptVersionCreate(
            version="v1",
            content=json.dumps({
                "system": "你需要把金融长文凝练为 3 张小红书图文卡片所需的核心观点文案，每张不超过 40 字。",
                "user_template": "长文如下：\n{{draft_article}}\n请输出 JSON 对象，例如 {{\"prompts\": [\"观点 1\", \"观点 2\", \"观点 3\"]}}",
            }, ensure_ascii=False),
            variables_schema={
                "type": "object",
                "properties": {"draft_article": {"type": "string"}},
                "required": ["draft_article"],
            },
            status="published",
        ),
    )
    await _ensure_prompt(
        PromptCreate(
            project_id="finance_media",
            prompt_key="xhs_copy_writer",
            name="小红书文案生成 Prompt",
            description="将金融长文转化为小红书爆款帖子",
            default_version="v1",
        ),
        PromptVersionCreate(
            version="v1",
            content=json.dumps({
                "system": "你是小红书爆款金融内容创作者，擅长把专业分析转化为普通投资者爱看的帖子。格式要求：第一行：抓眼球的标题（带 emoji，不超过 20 字），空一行后写正文：分 3-5 段，每段 2-4 句，语气轻松有温度，适量使用 emoji（每段 1-2 个，不滥用），最后一行：5-8 个话题标签，# 开头，空格分隔，总字数 250-450 字。",
                "user_template": "选题：{{selected_topic}}\n\n参考长文（提炼精华，勿照搬原文）：\n{{draft_article}}\n\n请直接输出小红书帖子正文。",
            }, ensure_ascii=False),
            variables_schema={
                "type": "object",
                "properties": {
                    "selected_topic": {"type": "string"},
                    "draft_article": {"type": "string"},
                },
                "required": ["selected_topic", "draft_article"],
            },
            status="published",
        ),
    )
    await _ensure_prompt(
        PromptCreate(
            project_id="finance_media",
            prompt_key="finance.article.draft",
            name="金融文章生成 Prompt（旧版）",
            description="用于根据选题和证据材料生成长文（向后兼容）",
            default_version="v1",
        ),
        PromptVersionCreate(
            version="v1",
            content=json.dumps({
                "system": "你是金融领域撰稿人",
                "user_template": "选题：{{topic}}\n证据：{{evidence}}\n目标受众：{{target_audience}}\n请输出一篇结构清晰的金融长文。",
            }, ensure_ascii=False),
            variables_schema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "evidence": {"type": "string"},
                    "target_audience": {"type": "string"},
                },
                "required": ["topic", "evidence"],
            },
            status="published",
        ),
    )
    await _ensure_prompt(
        PromptCreate(
            project_id="aigc_rtc",
            prompt_key="aigc.voice.persona.default",
            name="智能客服基础人设 Prompt",
            description="session 模式下创建上下文时使用的基础人设",
            default_version="v1",
        ),
        PromptVersionCreate(
            version="v1",
            content="你是一名通用智能助手，请用简洁、口语化的中文回答用户问题，便于语音播报。\n\n通用规则：\n1. 如果当轮用户消息里带有【参考资料】段，请优先依据其中内容作答，忠于原意，不要编造未提及的数据、专有名词。\n2. 资料未覆盖的部分可基于常识谨慎补充，并提示\"具体情况建议进一步核实\"。\n3. 当轮未提供参考资料时，基于通用知识作答，若超出能力范围请诚实告知。\n4. 回答中不要暴露\"参考资料\"四个字或片段编号，直接用自然语言回答。\n5. 善用对话历史，理解用户的指代和追问。",
            variables_schema={"type": "object", "properties": {}, "required": []},
            status="published",
        ),
    )
    await _ensure_prompt(
        PromptCreate(
            project_id="aigc_rtc",
            prompt_key="aigc.voice.rag.with_context",
            name="智能客服 RAG 命中 Prompt",
            description="RAG 检索命中时用于构造 system prompt",
            default_version="v1",
        ),
        PromptVersionCreate(
            version="v1",
            content="你是一名通用智能助手，请用简洁、口语化的中文回答用户问题，便于语音播报。\n\n请优先根据下面【参考资料】回答：\n1. 答案要忠于资料原意，不要编造未提及的数据、专有名词。\n2. 若资料未完全覆盖问题，可以基于常识谨慎补充，并告知用户\"以上为参考信息，具体情况建议进一步核实\"。\n3. 不要在回答中暴露\"参考资料\"四个字或片段编号，直接给出自然语言回答即可。\n\n【参考资料】\n{{context}}",
            variables_schema={
                "type": "object",
                "properties": {"context": {"type": "string"}},
                "required": ["context"],
            },
            status="published",
        ),
    )
    await _ensure_prompt(
        PromptCreate(
            project_id="aigc_rtc",
            prompt_key="aigc.voice.rag.no_context",
            name="智能客服 RAG 未命中 Prompt",
            description="RAG 检索未命中时用于构造 system prompt",
            default_version="v1",
        ),
        PromptVersionCreate(
            version="v1",
            content="你是一名通用智能助手，请用简洁、口语化的中文回答用户问题，便于语音播报。\n\n本次未在知识库中检索到与用户问题相关的资料。请遵守以下规则：\n1. 可以基于通用知识回答，但不要编造无法确认的具体数据或专有信息。\n2. 若问题超出能力范围，诚实告知用户并给出方向性建议。",
            variables_schema={"type": "object", "properties": {}, "required": []},
            status="published",
        ),
    )
    await _ensure_knowledge_base(
        KnowledgeBaseCreate(
            project_id="aigc_rtc",
            env="dev",
            kb_id="aigc_voice_kb",
            name="智能客服本地知识库",
            description="用于 RTC 智能客服本地 PostgreSQL RAG 检索",
            permission_scope="private",
        )
    )
    await _ensure_document(
        DocumentCreate(
            project_id="aigc_rtc",
            env="dev",
            kb_id="aigc_voice_kb",
            source_type="manual_text",
            title="退款政策",
            content="退款政策：用户购买服务后，如未产生实际使用记录，可在 7 天内申请无理由退款。若服务已经开始使用，客服会根据实际使用时长和合同条款核算可退金额。退款通常在审核通过后的 3 到 5 个工作日原路退回。",
            metadata={"source": "seed", "published_at": "2026-06-13"},
        )
    )
    async with SessionLocal() as session:
        await backfill_embeddings(session)
    await _ensure_document(
        DocumentCreate(
            project_id="aigc_rtc",
            env="dev",
            kb_id="aigc_voice_kb",
            source_type="manual_text",
            title="人工客服转接",
            content="人工客服转接规则：当用户明确要求人工服务、投诉升级、账单争议、身份核验失败或连续两轮未解决问题时，应建议转接人工客服，并简要说明需要人工继续处理。",
            metadata={"source": "seed", "published_at": "2026-06-13"},
        )
    )


def main() -> None:
    asyncio.run(seed_dev_data())
    print("Seeded development data.")


if __name__ == "__main__":
    main()
