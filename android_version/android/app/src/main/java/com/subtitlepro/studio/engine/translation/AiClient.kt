package com.subtitlepro.studio.engine.translation

import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.subtitlepro.studio.data.model.AppConfig
import com.subtitlepro.studio.data.model.ProviderType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

object ModelPresets {
    val GEMINI = listOf(
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite-preview",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    )

    val OPENAI = listOf(
        "gpt-4o-mini",
        "gpt-4o",
        "o1-mini",
        "o1-preview",
        "gpt-4-turbo",
        "gpt-3.5-turbo"
    )

    val LMSTUDIO = listOf(
        "allam-7b-instruct-preview",
        "qwen2.5-7b-instruct",
        "llama-3.2-3b-instruct",
        "llama-3.1-8b-instruct",
        "mistral-7b-instruct-v0.3"
    )

    val OLLAMA = listOf(
        "llama3:latest",
        "qwen2.5:latest",
        "mistral:latest",
        "gemma2:latest",
        "deepseek-r1:latest",
        "phi3:latest"
    )

    val CUSTOM = listOf(
        "gpt-4o-mini",
        "gpt-4o",
        "deepseek-chat",
        "deepseek-reasoner",
        "llama-3.3-70b-instruct",
        "qwen-2.5-72b-instruct"
    )

    fun getPresets(type: ProviderType): List<String> {
        return when (type) {
            ProviderType.GEMINI -> GEMINI
            ProviderType.OPENAI -> OPENAI
            ProviderType.LMSTUDIO -> LMSTUDIO
            ProviderType.OLLAMA -> OLLAMA
            ProviderType.CUSTOM -> CUSTOM
        }
    }
}

class AiClient(private val config: AppConfig) {

    companion object {
        val sharedClient: OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(90, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    private val client = sharedClient
    private val gson = Gson()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    suspend fun sendChatCompletion(messages: List<ChatMessage>): String = withContext(Dispatchers.IO) {
        val (url, authHeader, modelName) = resolveProviderDetails()

        val jsonBody = JsonObject().apply {
            addProperty("model", modelName)
            addProperty("temperature", config.temperature)
            addProperty("top_p", config.topP)
            addProperty("max_tokens", config.maxTokens)
            addProperty("stream", false)

            val messagesArray = JsonArray()
            for (msg in messages) {
                val mObj = JsonObject()
                mObj.addProperty("role", msg.role)
                mObj.addProperty("content", msg.content)
                messagesArray.add(mObj)
            }
            add("messages", messagesArray)
        }

        val requestBuilder = Request.Builder()
            .url(url)
            .post(jsonBody.toString().toRequestBody(jsonMediaType))

        if (authHeader.isNotBlank()) {
            requestBuilder.header("Authorization", authHeader)
        }

        client.newCall(requestBuilder.build()).execute().use { response ->
            val responseBody = response.body?.string() ?: ""

            if (!response.isSuccessful) {
                throw Exception("API Error (${response.code}): $responseBody")
            }

            val root = gson.fromJson(responseBody, JsonObject::class.java)
            val choices = root.getAsJsonArray("choices")
            if (choices != null && choices.size() > 0) {
                val firstChoice = choices[0].asJsonObject
                val message = firstChoice.getAsJsonObject("message")
                return@withContext message.get("content")?.asString ?: ""
            }

            throw Exception("Invalid response structure from LLM provider: $responseBody")
        }
    }

    suspend fun testConnection(): String = withContext(Dispatchers.IO) {
        val messages = listOf(ChatMessage("user", "Hello! Return word OK."))
        val reply = sendChatCompletion(messages)
        return@withContext "نجح الاتصال بالمزود بنجاح! رد النموذج: ${reply.take(50)}"
    }

    suspend fun fetchAvailableModels(): List<String> = withContext(Dispatchers.IO) {
        val presets = ModelPresets.getPresets(config.providerType)
        try {
            when (config.providerType) {
                ProviderType.GEMINI -> {
                    val key = config.geminiApiKey.trim()
                    if (key.isBlank()) return@withContext presets
                    val url = "https://generativelanguage.googleapis.com/v1beta/openai/models"
                    val request = Request.Builder()
                        .url(url)
                        .header("Authorization", "Bearer $key")
                        .get()
                        .build()
                    client.newCall(request).execute().use { response ->
                        val body = response.body?.string() ?: ""
                        if (response.isSuccessful) {
                            val root = gson.fromJson(body, JsonObject::class.java)
                            val data = root.getAsJsonArray("data")
                            val models = mutableListOf<String>()
                            if (data != null) {
                                for (elem in data) {
                                    val id = elem.asJsonObject.get("id")?.asString ?: ""
                                    if (id.isNotBlank()) {
                                        val clean = id.removePrefix("models/")
                                        if (!models.contains(clean)) models.add(clean)
                                    }
                                }
                            }
                            if (models.isNotEmpty()) return@withContext models
                        }
                    }
                }
                ProviderType.OPENAI -> {
                    val key = config.openaiApiKey.trim()
                    if (key.isBlank()) return@withContext presets
                    val url = "https://api.openai.com/v1/models"
                    val request = Request.Builder()
                        .url(url)
                        .header("Authorization", "Bearer $key")
                        .get()
                        .build()
                    client.newCall(request).execute().use { response ->
                        val body = response.body?.string() ?: ""
                        if (response.isSuccessful) {
                            val root = gson.fromJson(body, JsonObject::class.java)
                            val data = root.getAsJsonArray("data")
                            val models = mutableListOf<String>()
                            if (data != null) {
                                for (elem in data) {
                                    val id = elem.asJsonObject.get("id")?.asString ?: ""
                                    if (id.isNotBlank() && (id.contains("gpt") || id.contains("o1") || id.contains("o3") || id.contains("chat"))) {
                                        if (!models.contains(id)) models.add(id)
                                    }
                                }
                            }
                            if (models.isNotEmpty()) return@withContext models
                        }
                    }
                }
                ProviderType.LMSTUDIO -> {
                    val base = config.lmstudioUrl.trimEnd('/')
                    val rootUrl = if (base.endsWith("/v1")) base.removeSuffix("/v1") else base
                    val url = "$rootUrl/v1/models"
                    val request = Request.Builder().url(url).get().build()
                    client.newCall(request).execute().use { response ->
                        val body = response.body?.string() ?: ""
                        if (response.isSuccessful) {
                            val root = gson.fromJson(body, JsonObject::class.java)
                            val data = root.getAsJsonArray("data")
                            val models = mutableListOf<String>()
                            if (data != null) {
                                for (elem in data) {
                                    val id = elem.asJsonObject.get("id")?.asString ?: ""
                                    if (id.isNotBlank() && !models.contains(id)) models.add(id)
                                }
                            }
                            if (models.isNotEmpty()) return@withContext models
                        }
                    }
                }
                ProviderType.OLLAMA -> {
                    val base = config.ollamaUrl.trimEnd('/')
                    val rootUrl = if (base.endsWith("/v1")) base.removeSuffix("/v1") else base
                    val url = "$rootUrl/api/tags"
                    val request = Request.Builder().url(url).get().build()
                    client.newCall(request).execute().use { response ->
                        val body = response.body?.string() ?: ""
                        if (response.isSuccessful) {
                            val root = gson.fromJson(body, JsonObject::class.java)
                            val data = root.getAsJsonArray("models")
                            val models = mutableListOf<String>()
                            if (data != null) {
                                for (elem in data) {
                                    val name = elem.asJsonObject.get("name")?.asString ?: ""
                                    if (name.isNotBlank() && !models.contains(name)) models.add(name)
                                }
                            }
                            if (models.isNotEmpty()) return@withContext models
                        }
                    }
                }
                ProviderType.CUSTOM -> {
                    val base = config.customUrl.trimEnd('/')
                    val rootUrl = if (base.endsWith("/chat/completions")) base.removeSuffix("/chat/completions") else base
                    val url = if (rootUrl.endsWith("/models")) rootUrl else "$rootUrl/models"
                    val reqBuilder = Request.Builder().url(url).get()
                    if (config.customApiKey.isNotBlank()) {
                        reqBuilder.header("Authorization", "Bearer ${config.customApiKey.trim()}")
                    }
                    client.newCall(reqBuilder.build()).execute().use { response ->
                        val body = response.body?.string() ?: ""
                        if (response.isSuccessful) {
                            val root = gson.fromJson(body, JsonObject::class.java)
                            val data = root.getAsJsonArray("data")
                            val models = mutableListOf<String>()
                            if (data != null) {
                                for (elem in data) {
                                    val id = elem.asJsonObject.get("id")?.asString ?: ""
                                    if (id.isNotBlank() && !models.contains(id)) models.add(id)
                                }
                            }
                            if (models.isNotEmpty()) return@withContext models
                        }
                    }
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return@withContext presets
    }

    private fun resolveProviderDetails(): Triple<String, String, String> {
        return when (config.providerType) {
            ProviderType.GEMINI -> {
                val url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
                val auth = if (config.geminiApiKey.isNotBlank()) "Bearer ${config.geminiApiKey.trim()}" else ""
                val model = if (config.geminiModel.isNotBlank()) config.geminiModel else "gemini-2.5-flash"
                Triple(url, auth, model)
            }
            ProviderType.OPENAI -> {
                val url = "https://api.openai.com/v1/chat/completions"
                val auth = if (config.openaiApiKey.isNotBlank()) "Bearer ${config.openaiApiKey.trim()}" else ""
                val model = if (config.openaiModel.isNotBlank()) config.openaiModel else "gpt-4o-mini"
                Triple(url, auth, model)
            }
            ProviderType.LMSTUDIO -> {
                val base = config.lmstudioUrl.trimEnd('/')
                val url = if (base.endsWith("/chat/completions")) base else "$base/chat/completions"
                val model = if (config.lmstudioModel.isNotBlank()) config.lmstudioModel else "local-model"
                Triple(url, "", model)
            }
            ProviderType.OLLAMA -> {
                val base = config.ollamaUrl.trimEnd('/')
                val url = if (base.endsWith("/v1")) "$base/chat/completions" else "$base/v1/chat/completions"
                val model = if (config.ollamaModel.isNotBlank()) config.ollamaModel else "llama3"
                Triple(url, "", model)
            }
            ProviderType.CUSTOM -> {
                val base = config.customUrl.trimEnd('/')
                val url = if (base.endsWith("/chat/completions")) base else "$base/chat/completions"
                val auth = if (config.customApiKey.isNotBlank()) "Bearer ${config.customApiKey.trim()}" else ""
                val model = if (config.customModel.isNotBlank()) config.customModel else "default"
                Triple(url, auth, model)
            }
        }
    }
}
