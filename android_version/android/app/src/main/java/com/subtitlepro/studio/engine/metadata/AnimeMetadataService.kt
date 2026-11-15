package com.subtitlepro.studio.engine.metadata

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.subtitlepro.studio.data.model.AnimeMetadata
import com.subtitlepro.studio.data.model.CharacterProfile
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class AnimeMetadataService {

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    private val gson = Gson()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    suspend fun searchAnime(query: String): AnimeMetadata? = withContext(Dispatchers.IO) {
        if (query.isBlank()) return@withContext null

        val graphqlQuery = """
            query (${'$'}search: String) {
              Media (search: ${'$'}search, type: ANIME) {
                id
                title {
                  romaji
                  english
                  native
                }
                episodes
                coverImage {
                  large
                }
                characters (perPage: 25) {
                  edges {
                    role
                    node {
                      id
                      name {
                        full
                        native
                      }
                      gender
                    }
                    voiceActors (language: JAPANESE) {
                      name {
                        full
                      }
                    }
                  }
                }
              }
            }
        """.trimIndent()

        val jsonBody = JsonObject().apply {
            addProperty("query", graphqlQuery)
            val vars = JsonObject().apply {
                addProperty("search", query)
            }
            add("variables", vars)
        }

        val request = Request.Builder()
            .url("https://graphql.anilist.co")
            .post(jsonBody.toString().toRequestBody(jsonMediaType))
            .build()

        try {
            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: return@withContext null
            val root = gson.fromJson(body, JsonObject::class.java)

            val media = root.getAsJsonObject("data")?.getAsJsonObject("Media") ?: return@withContext null
            val titleObj = media.getAsJsonObject("title")
            val coverObj = media.getAsJsonObject("coverImage")

            val anime = AnimeMetadata(
                id = media.get("id")?.asInt ?: 0,
                titleRomaji = titleObj?.get("romaji")?.asString ?: "",
                titleEnglish = titleObj?.get("english")?.asString ?: "",
                titleNative = titleObj?.get("native")?.asString ?: "",
                episodes = media.get("episodes")?.asInt ?: 0,
                coverImageUrl = coverObj?.get("large")?.asString ?: ""
            )

            val charEdges = media.getAsJsonObject("characters")?.getAsJsonArray("edges")
            if (charEdges != null) {
                for (edgeElem in charEdges) {
                    val edge = edgeElem.asJsonObject
                    val node = edge.getAsJsonObject("node") ?: continue
                    val nameObj = node.getAsJsonObject("name")
                    val vaArray = edge.getAsJsonArray("voiceActors")
                    val vaName = if (vaArray != null && vaArray.size() > 0) {
                        vaArray[0].asJsonObject.getAsJsonObject("name")?.get("full")?.asString ?: ""
                    } else ""

                    val charId = node.get("id")?.asInt ?: 0
                    val fullName = nameObj?.get("full")?.asString ?: ""
                    val nativeName = nameObj?.get("native")?.asString ?: ""
                    val genderRaw = node.get("gender")?.asString ?: "UNKNOWN"
                    val role = edge.get("role")?.asString ?: "MAIN"

                    anime.characters.add(
                        CharacterProfile(
                            id = charId,
                            canonicalName = fullName,
                            nativeName = nativeName,
                            arabicName = "",
                            gender = genderRaw.uppercase(),
                            role = role,
                            voiceActor = vaName
                        )
                    )
                }
            }

            return@withContext anime
        } catch (e: Exception) {
            e.printStackTrace()
            return@withContext null
        }
    }
}
