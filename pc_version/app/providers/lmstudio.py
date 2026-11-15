import httpx
from typing import List, Optional
from app.models.provider import ModelInfo, ChatMessage, ChatResponse, ProviderConfig
from app.providers.base import ProviderBase
from app.core.exceptions import ProviderError, ConnectionError

class LMStudioProvider(ProviderBase):
    """LM Studio provider using OpenAI compatible endpoints and native LM Studio v0 endpoints."""
    
    def __init__(self, config: ProviderConfig):
        if not config.base_url:
            config.base_url = "http://localhost:1234/v1"
        config.base_url = config.base_url.rstrip("/")
        super().__init__(config)
        
    async def list_models(self) -> List[ModelInfo]:
        client = await self.get_client()
        # 1. Try native LM Studio v0 API to get rich loaded state information
        root_url = self.base_url
        if root_url.endswith("/v1"):
            root_url = root_url[:-3]
        v0_url = f"{root_url}/api/v0/models"
        
        try:
            resp = await client.get(v0_url, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                raw_list = data.get("data", [])
                loaded_models: List[ModelInfo] = []
                other_models: List[ModelInfo] = []
                for item in raw_list:
                    if not isinstance(item, dict):
                        continue
                    # Skip embedding models for translation
                    if item.get("type") == "embeddings":
                        continue
                    m_id = item.get("id") or str(item)
                    state = item.get("state", "not-loaded")
                    loaded_ctx = item.get("loaded_context_length")
                    
                    m_type = str(item.get("type", "")).lower()
                    m_lower = m_id.lower()
                    is_vlm = m_type == "vlm" or "vlm" in m_lower or "vision" in m_lower
                    is_allam = "allam" in m_lower
                    is_rec = is_allam or any(k in m_lower for k in ("qwen2.5", "qwen-2.5", "aya", "llama-3.1", "llama-3"))

                    rec_badge = " ⭐ موصى به" if is_rec else ""
                    if is_allam:
                        rec_badge = " 🇸🇦 موصى به (علام العربي)"
                    elif is_vlm:
                        rec_badge = " ⚠️ نموذج صور"

                    ctx_val = loaded_ctx or item.get("max_context_length") or (4096 if is_allam else None)

                    if state == "loaded":
                        ctx_info = f" ({ctx_val} ctx)" if ctx_val else ""
                        disp_name = f"{m_id} [{rec_badge.strip()} جاهز ومحمّل{ctx_info}]"
                        loaded_models.append(ModelInfo(
                            id=m_id,
                            name=disp_name.replace("  ", " "),
                            context_length=ctx_val
                        ))
                    else:
                        suffix = "غير مخصص للنصوص" if is_vlm else "يحتاج تحميل في LM Studio"
                        tag = f"{rec_badge} - {suffix}" if rec_badge else suffix
                        disp_name = f"{m_id} [{tag.strip()}]"
                        other_models.append(ModelInfo(
                            id=m_id,
                            name=disp_name.replace("  ", " "),
                            context_length=ctx_val
                        ))
                # Put already loaded models first for convenience
                if loaded_models or other_models:
                    return loaded_models + other_models
        except Exception:
            pass

        # 2. Standard OpenAI-compatible /v1/models fallback
        url = f"{self.base_url}/models"
        try:
            response = await client.get(url, timeout=5.0)
            response.raise_for_status()
            data = response.json()
            models = []
            raw_list = data.get("data", []) or data.get("models", [])
            if isinstance(data, list):
                raw_list = data

            for item in raw_list:
                if isinstance(item, dict):
                    m_id = item.get("id") or item.get("name") or str(item)
                    if item.get("type") == "embeddings":
                        continue
                else:
                    m_id = str(item)
                models.append(ModelInfo(
                    id=m_id,
                    name=m_id,
                    context_length=item.get("context_length") if isinstance(item, dict) else None
                ))
            return models
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to LM Studio at {url}: {e}")
        except Exception as e:
            raise ProviderError(f"Error listing LM Studio models: {e}")

    async def chat_completion(
        self, 
        messages: List[ChatMessage], 
        model: str, 
        temperature: float = 0.1, 
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = 0.85,
        min_p: Optional[float] = 0.05,
        repetition_penalty: Optional[float] = 1.0
    ) -> ChatResponse:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature if temperature is not None else 0.1,
            "top_p": top_p if top_p is not None else 0.85,
            "min_p": min_p if min_p is not None else 0.05,
            "repetition_penalty": repetition_penalty if repetition_penalty is not None else 1.0,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "stream": False
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
            
        try:
            client = await self.get_client()
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            choice_msg = data["choices"][0]["message"]
            content = choice_msg.get("content") or ""
            reasoning = choice_msg.get("reasoning_content") or ""

            # If content is empty (e.g. reasoning model consumed output tokens in thinking)
            if not content.strip() and reasoning.strip():
                content = reasoning

            usage = data.get("usage", {})
            
            return ChatResponse(
                content=content,
                model=model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0)
            )
        except httpx.HTTPStatusError as e:
            error_msg = e.response.text
            err_lower = error_msg.lower()
            if any(k in err_lower for k in ("failed to load model", "engine protocol startup was aborted", "failed to start engine")):
                raise ProviderError(
                    f"تعذر تشغيل النموذج '{model}' في LM Studio: الذاكرة (VRAM) غير كافية أو هناك نموذج آخر يمنع التحميل.\n"
                    f"💡 الحل: افتح LM Studio وقم بإلغاء تحميل النماذج السابقة (Eject/Unload) لإنعاش الذاكرة."
                )
            if e.response.status_code == 500:
                raise ProviderError(
                    f"خطأ 500 من LM Studio: قد يكون حجم سياق النموذج (Context Length) في LM Studio غير كافٍ أو تجاوز سعة VRAM.\n"
                    f"التفاصيل: {error_msg}"
                )
            raise ProviderError(f"HTTP {e.response.status_code} Error from LM Studio: {error_msg}")
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to LM Studio: {e}")
        except Exception as e:
            raise ProviderError(f"Error in LM Studio chat completion: {e}")

    async def test_connection(self) -> bool:
        try:
            await self.list_models()
            return True
        except Exception:
            return False
