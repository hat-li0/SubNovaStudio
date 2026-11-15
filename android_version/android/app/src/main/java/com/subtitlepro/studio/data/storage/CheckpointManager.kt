package com.subtitlepro.studio.data.storage

import android.content.Context
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.subtitlepro.studio.data.model.SubtitleDocument
import com.subtitlepro.studio.data.model.SubtitleEvent
import java.io.File

data class CheckpointData(
    val fileName: String,
    val completedBatches: Int,
    val totalBatches: Int,
    val events: List<SubtitleEvent>,
    val timestamp: Long = System.currentTimeMillis()
)

object CheckpointManager {

    private val gson: Gson = GsonBuilder().setPrettyPrinting().create()

    private fun getCheckpointDir(context: Context): File {
        val dir = File(context.filesDir, "checkpoints")
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    private fun getCheckpointFile(context: Context, fileName: String): File {
        val safeName = fileName.replace("[^a-zA-Z0-9_.-]".toRegex(), "_")
        return File(getCheckpointDir(context), "${safeName}.checkpoint.json")
    }

    fun saveCheckpoint(
        context: Context,
        doc: SubtitleDocument,
        completedBatches: Int,
        totalBatches: Int
    ) {
        val fName = doc.fileName ?: "untitled_session"
        try {
            val data = CheckpointData(
                fileName = fName,
                completedBatches = completedBatches,
                totalBatches = totalBatches,
                events = doc.events
            )
            val json = gson.toJson(data)
            getCheckpointFile(context, fName).writeText(json, Charsets.UTF_8)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun loadCheckpoint(context: Context, fileName: String): CheckpointData? {
        return try {
            val file = getCheckpointFile(context, fileName)
            if (!file.exists()) return null
            val json = file.readText(Charsets.UTF_8)
            gson.fromJson(json, CheckpointData::class.java)
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    fun hasCheckpoint(context: Context, fileName: String): Boolean {
        return getCheckpointFile(context, fileName).exists()
    }

    fun clearCheckpoint(context: Context, fileName: String) {
        try {
            val file = getCheckpointFile(context, fileName)
            if (file.exists()) {
                file.delete()
            }
        } catch (ignored: Exception) {}
    }
}
