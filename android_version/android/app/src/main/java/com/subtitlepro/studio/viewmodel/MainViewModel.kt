package com.subtitlepro.studio.viewmodel

import android.app.Application
import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import androidx.core.content.FileProvider
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.subtitlepro.studio.data.model.AnimeMetadata
import com.subtitlepro.studio.data.model.AppConfig
import com.subtitlepro.studio.data.model.CharacterProfile
import com.subtitlepro.studio.data.model.GlossaryEntry
import com.subtitlepro.studio.data.model.SubtitleDocument
import com.subtitlepro.studio.data.model.SubtitleEvent
import com.subtitlepro.studio.data.model.SubtitleFormat
import com.subtitlepro.studio.data.model.SubtitleStreamInfo
import com.subtitlepro.studio.data.model.TranslationStatus
import com.subtitlepro.studio.data.parser.SubtitleManager
import com.subtitlepro.studio.data.storage.CheckpointManager
import com.subtitlepro.studio.data.video.VideoSubtitleExtractor
import com.subtitlepro.studio.engine.healer.SubtitleHealer
import com.subtitlepro.studio.engine.metadata.AnimeMetadataService
import com.subtitlepro.studio.engine.service.TranslationForegroundService
import com.subtitlepro.studio.engine.translation.AiClient
import com.subtitlepro.studio.engine.translation.TranslationPipeline
import kotlinx.coroutines.Job
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.File
import java.io.FileOutputStream

class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val _config = MutableStateFlow(AppConfig())
    val config: StateFlow<AppConfig> = _config.asStateFlow()

    private val _document = MutableStateFlow<SubtitleDocument?>(null)
    val document: StateFlow<SubtitleDocument?> = _document.asStateFlow()

    private val _status = MutableStateFlow(TranslationStatus.IDLE)
    val status: StateFlow<TranslationStatus> = _status.asStateFlow()

    private val _progress = MutableStateFlow(0f)
    val progress: StateFlow<Float> = _progress.asStateFlow()

    private val _progressMessage = MutableStateFlow("جاهز للاستخدام")
    val progressMessage: StateFlow<String> = _progressMessage.asStateFlow()

    private val _logs = MutableStateFlow<List<String>>(emptyList())
    val logs: StateFlow<List<String>> = _logs.asStateFlow()

    private val _animeMetadata = MutableStateFlow<AnimeMetadata?>(null)
    val animeMetadata: StateFlow<AnimeMetadata?> = _animeMetadata.asStateFlow()

    private val _characterList = MutableStateFlow<List<CharacterProfile>>(emptyList())
    val characterList: StateFlow<List<CharacterProfile>> = _characterList.asStateFlow()

    private val _glossaryList = MutableStateFlow<List<GlossaryEntry>>(emptyList())
    val glossaryList: StateFlow<List<GlossaryEntry>> = _glossaryList.asStateFlow()

    private val _videoTracks = MutableStateFlow<List<SubtitleStreamInfo>>(emptyList())
    val videoTracks: StateFlow<List<SubtitleStreamInfo>> = _videoTracks.asStateFlow()

    private val _showTrackDialog = MutableStateFlow(false)
    val showTrackDialog: StateFlow<Boolean> = _showTrackDialog.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _loadingMessage = MutableStateFlow("")
    val loadingMessage: StateFlow<String> = _loadingMessage.asStateFlow()

    private var currentVideoUri: Uri? = null
    private var translationJob: Job? = null
    private val metadataService = AnimeMetadataService()

    init {
        log("✨ مرحباً بك في SubNova Studio — استوديو سوب نوفا للترجمة الفائقة.")
        log("🚀 تم تجهيز محرك التنقية الذاتي ومزودات الذكاء الاصطناعي بنجاح.")
    }

    fun log(msg: String) {
        val current = _logs.value
        _logs.value = if (current.size >= 500) {
            (current.takeLast(400) + msg)
        } else {
            current + msg
        }
    }

    fun clearLogs() {
        _logs.value = emptyList()
    }

    fun updateConfig(block: AppConfig.() -> Unit) {
        val newConfig = _config.value.copy()
        newConfig.block()
        _config.value = newConfig
    }

    fun loadSubtitleFromUri(context: Context, uri: Uri, fileName: String) {
        viewModelScope.launch {
            _isLoading.value = true
            _loadingMessage.value = "جاري قراءة واستخراج ملف الترجمة: $fileName..."
            try {
                withContext(Dispatchers.IO) {
                    context.contentResolver.openInputStream(uri)?.use { stream ->
                        val reader = BufferedReader(InputStreamReader(stream))
                        val content = reader.readText()
                        val doc = SubtitleManager.parse(content, fileName)
                        
                        // Check for existing checkpoint
                        val checkpoint = CheckpointManager.loadCheckpoint(context, fileName)
                        if (checkpoint != null && checkpoint.events.any { !it.translatedText.isNullOrBlank() }) {
                            val restoredCount = checkpoint.events.count { !it.translatedText.isNullOrBlank() }
                            for (cpEv in checkpoint.events) {
                                val target = doc.events.firstOrNull { it.id == cpEv.id }
                                if (target != null && !cpEv.translatedText.isNullOrBlank()) {
                                    target.translatedText = cpEv.translatedText
                                }
                            }
                            log("🔄 تم استعادة $restoredCount سطراً مترجماً تلقائياً من نقطة الحفظ السابقة (Checkpoint)!")
                        }

                        _document.value = doc
                        _progress.value = 0f
                        _progressMessage.value = "تم تحميل ${doc.events.size} سطر ترجمة بنجاح."
                        log("📁 تم استيراد ملف الترجمة: $fileName (${doc.events.size} سطر، الصيغة: ${doc.format.displayName})")
                    }
                }
            } catch (e: Exception) {
                log("❌ خطأ أثناء قراءة ملف الترجمة: ${e.message}")
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun loadSubtitleFile(content: String, fileName: String) {
        viewModelScope.launch {
            _isLoading.value = true
            _loadingMessage.value = "جاري تحليل أسطر الترجمة..."
            try {
                withContext(Dispatchers.IO) {
                    val doc = SubtitleManager.parse(content, fileName)
                    val checkpoint = CheckpointManager.loadCheckpoint(getApplication(), fileName)
                    if (checkpoint != null && checkpoint.events.any { !it.translatedText.isNullOrBlank() }) {
                        val restoredCount = checkpoint.events.count { !it.translatedText.isNullOrBlank() }
                        for (cpEv in checkpoint.events) {
                            val target = doc.events.firstOrNull { it.id == cpEv.id }
                            if (target != null && !cpEv.translatedText.isNullOrBlank()) {
                                target.translatedText = cpEv.translatedText
                            }
                        }
                        log("🔄 تم استعادة $restoredCount سطراً مترجماً تلقائياً من نقطة الحفظ السابقة (Checkpoint)!")
                    }

                    _document.value = doc
                    _progress.value = 0f
                    _progressMessage.value = "تم تحميل ${doc.events.size} سطر ترجمة بنجاح."
                    log("📁 تم تحميل ملف الترجمة: $fileName (${doc.events.size} سطر، الصيغة: ${doc.format.displayName})")
                }
            } catch (e: Exception) {
                log("❌ خطأ أثناء قراءة ملف الترجمة: ${e.message}")
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun handleVideoFile(context: Context, uri: Uri, fileName: String) {
        currentVideoUri = uri
        viewModelScope.launch {
            _isLoading.value = true
            _loadingMessage.value = "جاري فحص مسارات الترجمة المدمجة داخل الفيديو..."
            log("🎬 تم تحديد ملف فيديو: $fileName. جاري فحص مسارات الترجمة المدمجة...")
            try {
                val tracks = withContext(Dispatchers.IO) {
                    VideoSubtitleExtractor.probeSubtitleTracks(context, uri)
                }
                _videoTracks.value = tracks
                if (tracks.isEmpty()) {
                    log("⚠️ لم يتم العثور على مسارات ترجمة نصية مدمجة داخل الفيديو.")
                    _progressMessage.value = "فيديو بدون مسارات ترجمة مدمجة."
                } else if (tracks.size == 1) {
                    log("🔍 تم العثور على مسار ترجمة واحد. جاري استخراجه تلقائياً...")
                    _loadingMessage.value = "جاري استخراج مسار الترجمة بالكامل من الفيديو..."
                    extractTrackInternal(context, 0, fileName)
                } else {
                    log("✨ تم العثور على ${tracks.size} مسارات ترجمة داخل الفيديو. يُرجى اختيار المسار المطلوب.")
                    _showTrackDialog.value = true
                }
            } catch (e: Exception) {
                log("❌ خطأ أثناء فحص الفيديو: ${e.message}")
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun selectTrack(context: Context, trackIndex: Int, videoFileName: String) {
        _showTrackDialog.value = false
        viewModelScope.launch {
            _isLoading.value = true
            _loadingMessage.value = "جاري استخراج مسار الترجمة رقم ${trackIndex + 1} من الفيديو وقراءة الأسطر..."
            try {
                extractTrackInternal(context, trackIndex, videoFileName)
            } catch (e: Exception) {
                log("❌ خطأ أثناء استخراج الترجمة: ${e.message}")
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun dismissTrackDialog() {
        _showTrackDialog.value = false
    }

    private suspend fun extractTrackInternal(context: Context, trackIndex: Int, videoFileName: String) {
        val uri = currentVideoUri ?: return
        log("⏳ جاري استخراج مسار الترجمة رقم ${trackIndex + 1}...")
        val doc = withContext(Dispatchers.IO) {
            VideoSubtitleExtractor.extractSubtitleTrack(context, uri, trackIndex)
        }
        val subName = videoFileName.substringBeforeLast('.') + ".ass"
        doc.fileName = subName
        _document.value = doc
        _progressMessage.value = "تم استخراج ${doc.events.size} سطر بنجاح."
        log("✅ تم استخراج ${doc.events.size} سطر من مسار الفيديو بنجاح!")
    }

    fun performQuickHealing() {
        val doc = _document.value ?: return
        viewModelScope.launch {
            _isLoading.value = true
            _loadingMessage.value = "جاري التنقية الفورية الذاتية لكافة وسوم وأسطر الترجمة..."
            try {
                var count = 0
                val cfg = _config.value
                withContext(Dispatchers.IO) {
                    for (ev in doc.events) {
                        val target = ev.translatedText ?: ev.originalText
                        if (target.isNotBlank()) {
                            val healed = SubtitleHealer.heal(
                                text = target,
                                originalText = ev.originalText,
                                enableArabicPunct = cfg.enableArabicPunct,
                                enableLatinClean = cfg.enableLatinClean,
                                enableQuoteFix = cfg.enableQuoteFix,
                                protectTags = cfg.protectTags
                            )
                            if (ev.translatedText != null) {
                                if (ev.translatedText != healed) {
                                    ev.translatedText = healed
                                    count++
                                }
                            } else {
                                if (ev.originalText != healed) {
                                    ev.originalText = healed
                                    count++
                                }
                            }
                        }
                    }
                }
                _document.value = doc.copy()
                log("✨ التنقية الفورية الذاتية (Zero-Token Healing): تم إصلاح وتنقية $count سطراً فورياً بدون استهلاك رموز!")
                _progressMessage.value = "تمت تنقية $count سطراً بنجاح."
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun startTranslation() {
        val doc = _document.value
        if (doc == null || doc.events.isEmpty()) {
            log("⚠️ الرجاء فتح ملف ترجمة أولاً قبل بدء المعالجة.")
            return
        }

        val cfg = _config.value
        val aiClient = AiClient(cfg)
        val pipeline = TranslationPipeline(cfg, aiClient)

        _status.value = TranslationStatus.TRANSLATING
        _progress.value = 0f

        val app = getApplication<Application>()
        val totalBatchesEst = (doc.events.size / cfg.batchSize.coerceIn(5, 50)).coerceAtLeast(1)

        // Start Foreground Service with WakeLock
        TranslationForegroundService.startService(
            context = app,
            currentBatch = 1,
            totalBatches = totalBatchesEst,
            processedLines = 0,
            totalLines = doc.events.size,
            message = "بدء خط المعالجة والترجمة..."
        )

        translationJob = viewModelScope.launch {
            try {
                pipeline.execute(
                    document = doc,
                    characters = _characterList.value,
                    glossary = _glossaryList.value,
                    onProgress = { pct, processed, total, msg ->
                        _progress.value = pct
                        _progressMessage.value = msg
                    },
                    onEventUpdated = { updatedEv ->
                        // Lightweight in-memory update, StateFlow is emitted on batch finish to avoid recomposition lag
                    },
                    onBatchCompleted = { bIdx, totalBatches, processedCount ->
                        // 1. Batch UI update: single recomposition per batch (Zero lag)
                        _document.value = doc.copy()
                        // 2. Persist checkpoint to disk (Guaranteed recovery on network drop)
                        CheckpointManager.saveCheckpoint(app, doc, bIdx, totalBatches)
                        // 3. Update Foreground Service notification
                        TranslationForegroundService.updateProgress(
                            context = app,
                            currentBatch = bIdx,
                            totalBatches = totalBatches,
                            processedLines = processedCount,
                            totalLines = doc.events.size,
                            message = "اكتملت الدفعة $bIdx من $totalBatches بنجاح"
                        )
                    },
                    onLog = { msg ->
                        log(msg)
                    }
                )
                _status.value = TranslationStatus.COMPLETED
                _document.value = doc.copy()
                CheckpointManager.clearCheckpoint(app, doc.fileName ?: "")
            } catch (e: Exception) {
                // Save checkpoint on any error so completed batches are never lost
                CheckpointManager.saveCheckpoint(app, doc, 0, 0)
                _document.value = doc.copy()

                if (e is kotlinx.coroutines.CancellationException) {
                    log("⏹ تم إيقاف عملية الترجمة من قِبل المستخدم. تم حفظ كافة الأسطر المترجمة كـ Checkpoint.")
                    _status.value = TranslationStatus.PAUSED
                } else {
                    log("❌ خطأ أثناء الترجمة: ${e.message}. تم حفظ كافة الأسطر المكتملة تلقائياً بنجاح.")
                    _status.value = TranslationStatus.ERROR
                }
            } finally {
                TranslationForegroundService.stopService(app)
            }
        }
    }

    fun cancelTranslation() {
        translationJob?.cancel()
        _status.value = TranslationStatus.PAUSED
        TranslationForegroundService.stopService(getApplication())
        log("⏹ تم إيقاف الترجمة.")
    }

    fun updateEventText(id: Int, newTranslated: String) {
        val doc = _document.value ?: return
        val ev = doc.events.firstOrNull { it.id == id } ?: return
        ev.translatedText = newTranslated
        _document.value = doc.copy()
    }

    fun searchAnime(query: String) {
        viewModelScope.launch {
            log("🔍 جاري البحث في قواعد بيانات الأنمي عن: $query...")
            val result = metadataService.searchAnime(query)
            if (result != null) {
                _animeMetadata.value = result
                _characterList.value = result.characters
                log("✅ تم جلب بيانات: ${result.titleRomaji} (${result.titleNative}) مع ${result.characters.size} شخصية.")
            } else {
                log("⚠️ لم يتم العثور على نتائج للبحث.")
            }
        }
    }

    fun addGlossaryTerm(source: String, target: String, notes: String) {
        if (source.isBlank() || target.isBlank()) return
        val entry = GlossaryEntry(source.trim(), target.trim(), notes.trim())
        _glossaryList.value = _glossaryList.value + listOf(entry)
        log("📖 أُضيف للمصطلحات: $source -> $target")
    }

    fun removeGlossaryTerm(entry: GlossaryEntry) {
        _glossaryList.value = _glossaryList.value.filter { it != entry }
    }

    fun updateCharacterProfile(updated: CharacterProfile) {
        _characterList.value = _characterList.value.map {
            if (it.id == updated.id) updated else it
        }
    }

    fun testAiConnection(onResult: (String) -> Unit) {
        viewModelScope.launch {
            try {
                log("🔄 جاري اختبار الاتصال بالمزود: ${_config.value.providerType.displayName}...")
                val client = AiClient(_config.value)
                val msg = client.testConnection()
                log("✅ $msg")
                onResult(msg)
            } catch (e: Exception) {
                val err = "فشل الاتصال: ${e.message}"
                log("❌ $err")
                onResult(err)
            }
        }
    }

    fun fetchModelsForCurrentProvider(onResult: (List<String>) -> Unit) {
        viewModelScope.launch {
            try {
                log("🔄 جاري جلب قائمة النماذج المتاحة من مزود ${_config.value.providerType.displayName}...")
                val client = AiClient(_config.value)
                val models = client.fetchAvailableModels()
                log("✅ تم العثور على ${models.size} نموذج متاح.")
                onResult(models)
            } catch (e: Exception) {
                log("⚠️ تعذر جلب النماذج تلقائياً: ${e.message}")
                onResult(emptyList())
            }
        }
    }

    private fun toUtf8WithBom(text: String): ByteArray {
        val bom = byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte())
        val bytes = text.toByteArray(Charsets.UTF_8)
        return bom + bytes
    }

    fun exportSubtitleFile(context: Context, format: SubtitleFormat): Uri? {
        val doc = _document.value ?: return null
        return try {
            val textContent = SubtitleManager.serialize(doc, format)
            val baseName = doc.fileName?.substringBeforeLast('.') ?: "translated_subtitles"
            val targetName = "${baseName}.ara${format.extension}"

            val exportDir = File(context.cacheDir, "exports")
            if (!exportDir.exists()) exportDir.mkdirs()
            val file = File(exportDir, targetName)
            FileOutputStream(file).use { it.write(toUtf8WithBom(textContent)) }

            val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
            log("💾 تم تصدير ملف الترجمة بنجاح: ${file.name}")
            uri
        } catch (e: Exception) {
            log("❌ خطأ أثناء تصدير الملف: ${e.message}")
            null
        }
    }

    fun saveSubtitleToDownloads(context: Context, format: SubtitleFormat): Boolean {
        val doc = _document.value ?: return false
        return try {
            val textContent = SubtitleManager.serialize(doc, format)
            val baseName = doc.fileName?.substringBeforeLast('.') ?: "translated_subtitles"
            val targetName = "${baseName}.ara${format.extension}"
            val dataBytes = toUtf8WithBom(textContent)

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val contentValues = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, targetName)
                    put(MediaStore.MediaColumns.MIME_TYPE, "text/plain")
                    put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                }
                val uri = context.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, contentValues)
                    ?: return false
                context.contentResolver.openOutputStream(uri)?.use { stream ->
                    stream.write(dataBytes)
                }
            } else {
                @Suppress("DEPRECATION")
                val downloadsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
                if (!downloadsDir.exists()) downloadsDir.mkdirs()
                val targetFile = File(downloadsDir, targetName)
                FileOutputStream(targetFile).use { it.write(dataBytes) }
            }
            log("✅ تم حفظ ملف الترجمة مباشرة في مجلد التنزيلات (Downloads): $targetName")
            true
        } catch (e: Exception) {
            log("❌ تعذر الحفظ في مجلد التنزيلات: ${e.message}")
            false
        }
    }

    fun exportSubtitleToUri(context: Context, destinationUri: Uri, format: SubtitleFormat): Boolean {
        val doc = _document.value ?: return false
        return try {
            val textContent = SubtitleManager.serialize(doc, format)
            context.contentResolver.openOutputStream(destinationUri)?.use { stream ->
                stream.write(toUtf8WithBom(textContent))
            }
            log("✅ تم حفظ ملف الترجمة بنجاح في المسار المحدد (SAF)!")
            true
        } catch (e: Exception) {
            log("❌ فشل حفظ الملف في المسار المختار: ${e.message}")
            false
        }
    }
}
