package com.subtitlepro.studio.ui.screens

import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.AutoFixHigh
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.VideoFile
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.subtitlepro.studio.data.model.SubtitleFormat
import com.subtitlepro.studio.data.model.TranslationStatus
import com.subtitlepro.studio.ui.theme.AmberAccent
import com.subtitlepro.studio.ui.theme.DangerRed
import com.subtitlepro.studio.ui.theme.DarkBorder
import com.subtitlepro.studio.ui.theme.DarkCard
import com.subtitlepro.studio.ui.theme.DarkSurface
import com.subtitlepro.studio.ui.theme.NeonCyan
import com.subtitlepro.studio.ui.theme.NeonGreen
import com.subtitlepro.studio.ui.theme.TextPrimary
import com.subtitlepro.studio.ui.theme.TextSecondary
import com.subtitlepro.studio.viewmodel.MainViewModel
import java.io.BufferedReader
import java.io.InputStreamReader

@Composable
fun StudioScreen(viewModel: MainViewModel) {
    val context = LocalContext.current
    val doc by viewModel.document.collectAsState()
    val status by viewModel.status.collectAsState()
    val progress by viewModel.progress.collectAsState()
    val progressMessage by viewModel.progressMessage.collectAsState()
    val config by viewModel.config.collectAsState()
    val videoTracks by viewModel.videoTracks.collectAsState()
    val showTrackDialog by viewModel.showTrackDialog.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val loadingMessage by viewModel.loadingMessage.collectAsState()

    var showExportDialog by remember { mutableStateOf(false) }
    var selectedVideoName by remember { mutableStateOf("") }
    var exportTargetFormat by remember { mutableStateOf(SubtitleFormat.ASS) }
    var showFormatActionDialog by remember { mutableStateOf(false) }

    // SAF Document Creator Launcher
    val safCreateDocLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument("text/plain")
    ) { destUri ->
        if (destUri != null) {
            viewModel.exportSubtitleToUri(context, destUri, exportTargetFormat)
        }
    }

    // Subtitle File Picker
    val subPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            val fileName = queryFileName(context, uri) ?: "subtitles.ass"
            viewModel.loadSubtitleFromUri(context, uri, fileName)
        }
    }

    // Video File Picker
    val videoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            val fileName = queryFileName(context, uri) ?: "video.mkv"
            selectedVideoName = fileName
            viewModel.handleVideoFile(context, uri, fileName)
        }
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // 0. Hero Brand Card with Developer Rights
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, NeonCyan.copy(alpha = 0.35f)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(46.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .background(DarkCard)
                            .border(1.dp, NeonCyan, RoundedCornerShape(12.dp)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.AutoAwesome,
                            contentDescription = null,
                            tint = AmberAccent,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = "SubNova Studio",
                                color = NeonCyan,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(DarkBorder)
                                    .padding(horizontal = 6.dp, vertical = 2.dp)
                            ) {
                                Text("v2.0", color = AmberAccent, fontSize = 9.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = "استوديو الترجمة والتنقية السينمائية الفائقة | تطوير: حاتم الحربي",
                            color = TextSecondary,
                            fontSize = 11.sp
                        )
                    }
                }
            }
        }

        // 1. File Selection Cards
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, DarkBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "📁 استيراد ملف العمل",
                        color = NeonCyan,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Button(
                            onClick = { subPickerLauncher.launch("*/*") },
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = NeonCyan,
                                contentColor = Color.Black
                            ),
                            shape = RoundedCornerShape(10.dp)
                        ) {
                            Icon(Icons.Default.Description, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("ملف ترجمة", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        }

                        Button(
                            onClick = { videoPickerLauncher.launch("video/*") },
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = NeonGreen,
                                contentColor = Color.Black
                            ),
                            shape = RoundedCornerShape(10.dp)
                        ) {
                            Icon(Icons.Default.VideoFile, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(6.dp))
                            Text("استخراج من فيديو", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        }
                    }
                }
            }
        }

        // 2. Loaded File Details (if any)
        item {
            if (doc != null) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = DarkCard),
                    shape = RoundedCornerShape(16.dp),
                    border = BorderStroke(1.dp, NeonCyan.copy(alpha = 0.4f)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                text = doc?.fileName ?: "ملف الترجمة",
                                color = TextPrimary,
                                fontSize = 15.sp,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.weight(1f)
                            )
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(DarkBorder)
                                    .padding(horizontal = 8.dp, vertical = 4.dp)
                            ) {
                                Text(
                                    text = doc?.format?.name ?: "ASS",
                                    color = AmberAccent,
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))
                        val eventsCount = doc?.events?.size ?: 0
                        val translatedCount = doc?.events?.count { it.translatedText != null } ?: 0

                        Text(
                            text = "إجمالي الأسطر: $eventsCount سطر حوار | المترجم: $translatedCount",
                            color = TextSecondary,
                            fontSize = 12.sp
                        )
                    }
                }
            }
        }

        // 3. Execution & Progress Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, DarkBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "⚡ خط الإنتاج والترجمة الفائقة",
                        color = TextPrimary,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    if (status == TranslationStatus.TRANSLATING || status == TranslationStatus.IMPROVING) {
                        LinearProgressIndicator(
                            progress = { progress / 100f },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(8.dp)
                                .clip(RoundedCornerShape(4.dp)),
                            color = NeonCyan,
                            trackColor = DarkBorder
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(text = progressMessage, color = TextSecondary, fontSize = 12.sp)
                            Text(text = "${progress.toInt()}%", color = NeonCyan, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                        }
                        Spacer(modifier = Modifier.height(16.dp))
                    } else {
                        Text(text = progressMessage, color = TextSecondary, fontSize = 13.sp)
                        Spacer(modifier = Modifier.height(12.dp))
                    }

                    // Translation controls
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        if (status == TranslationStatus.TRANSLATING || status == TranslationStatus.IMPROVING) {
                            Button(
                                onClick = { viewModel.cancelTranslation() },
                                colors = ButtonDefaults.buttonColors(containerColor = DangerRed),
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Icon(Icons.Default.Stop, contentDescription = null)
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("إيقاف مؤقت", fontWeight = FontWeight.Bold)
                            }
                        } else {
                            Button(
                                onClick = { viewModel.startTranslation() },
                                enabled = doc != null,
                                colors = ButtonDefaults.buttonColors(containerColor = NeonCyan, contentColor = Color.Black),
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Icon(Icons.Default.PlayArrow, contentDescription = null)
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("بدء الترجمة والتحسين", fontWeight = FontWeight.Bold)
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(10.dp))

                    // Instant Zero-Token Healing Button
                    OutlinedButton(
                        onClick = { viewModel.performQuickHealing() },
                        enabled = doc != null,
                        border = BorderStroke(1.dp, AmberAccent),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = AmberAccent),
                        shape = RoundedCornerShape(10.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.AutoFixHigh, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("تنقية فورية بدون استهلاك (Zero-Token Healing)", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }

        // 4. Quick Toggles
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, DarkBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "⚙️ خيارات المعالجة المباشرة",
                        color = TextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(10.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("المرحلة الثانية (التحسين والتدقيق الفائق)", color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                            Text("مراجعة صياغة العبارات وتجاوز ركاكة الترجمة الآلية", color = TextSecondary, fontSize = 11.sp)
                        }
                        Switch(
                            checked = config.autoImprove,
                            onCheckedChange = { viewModel.updateConfig { autoImprove = it } },
                            colors = SwitchDefaults.colors(checkedThumbColor = NeonCyan, checkedTrackColor = NeonCyan.copy(alpha = 0.5f))
                        )
                    }

                    HorizontalDivider(color = DarkBorder, modifier = Modifier.padding(vertical = 10.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("محرك التنقية الذاتي (Smart Auto-Healing)", color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                            Text("حصانة وسوم ASS وإزالة الشوائب وضبط الترقيم العربي", color = TextSecondary, fontSize = 11.sp)
                        }
                        Switch(
                            checked = config.enableSmartHealing,
                            onCheckedChange = { viewModel.updateConfig { enableSmartHealing = it } },
                            colors = SwitchDefaults.colors(checkedThumbColor = NeonGreen, checkedTrackColor = NeonGreen.copy(alpha = 0.5f))
                        )
                    }
                }
            }
        }

        // 5. Export & Share Card
        item {
            if (doc != null) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = DarkSurface),
                    shape = RoundedCornerShape(16.dp),
                    border = BorderStroke(1.dp, DarkBorder),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "💾 تصدير وحفظ الترجمة",
                            color = TextPrimary,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.height(10.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Button(
                                onClick = { showExportDialog = true },
                                modifier = Modifier.weight(1f),
                                colors = ButtonDefaults.buttonColors(containerColor = NeonGreen, contentColor = Color.Black),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Icon(Icons.Default.Download, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("تصدير وحفظ", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                            }

                            OutlinedButton(
                                onClick = {
                                    val uri = viewModel.exportSubtitleFile(context, SubtitleFormat.ASS)
                                    if (uri != null) {
                                        val shareIntent = Intent(Intent.ACTION_SEND).apply {
                                            type = "application/x-subrip"
                                            putExtra(Intent.EXTRA_STREAM, uri)
                                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                        }
                                        context.startActivity(Intent.createChooser(shareIntent, "مشاركة ملف الترجمة"))
                                    }
                                },
                                modifier = Modifier.weight(1f),
                                border = BorderStroke(1.dp, NeonCyan),
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = NeonCyan),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("مشاركة", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                            }
                        }
                    }
                }
            }
        }
    }

    // Video Track Selection Dialog
    if (showTrackDialog && videoTracks.isNotEmpty()) {
        AlertDialog(
            onDismissRequest = { viewModel.dismissTrackDialog() },
            containerColor = DarkSurface,
            title = {
                Text(
                    text = "اختر مسار الترجمة من الفيديو",
                    color = NeonCyan,
                    fontWeight = FontWeight.Bold,
                    fontSize = 17.sp
                )
            },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "عُثر على ${videoTracks.size} مسارات ترجمة داخل الفيديو:",
                        color = TextSecondary,
                        fontSize = 13.sp
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    videoTracks.forEach { track ->
                        Card(
                            colors = CardDefaults.cardColors(containerColor = DarkCard),
                            shape = RoundedCornerShape(10.dp),
                            border = BorderStroke(1.dp, DarkBorder),
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    viewModel.selectTrack(context, track.index, selectedVideoName)
                                }
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text(
                                    text = track.displayName(),
                                    color = TextPrimary,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Medium
                                )
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { viewModel.dismissTrackDialog() }) {
                    Text("إلغاء", color = DangerRed)
                }
            }
        )
    }

    // Export Format Dialog
    if (showExportDialog) {
        AlertDialog(
            onDismissRequest = { showExportDialog = false },
            containerColor = DarkSurface,
            title = {
                Text("اختر صيغة التصدير", color = NeonGreen, fontWeight = FontWeight.Bold)
            },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(SubtitleFormat.ASS, SubtitleFormat.SRT, SubtitleFormat.VTT, SubtitleFormat.TXT).forEach { fmt ->
                        Card(
                            colors = CardDefaults.cardColors(containerColor = DarkCard),
                            shape = RoundedCornerShape(10.dp),
                            border = BorderStroke(1.dp, DarkBorder),
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    exportTargetFormat = fmt
                                    showExportDialog = false
                                    showFormatActionDialog = true
                                }
                        ) {
                            Row(
                                modifier = Modifier.padding(14.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(fmt.displayName, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                                Icon(Icons.Default.Download, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(18.dp))
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showExportDialog = false }) {
                    Text("إلغاء", color = TextSecondary)
                }
            }
        )
    }

    // Export Action Location Dialog (Downloads vs Custom SAF vs Share)
    if (showFormatActionDialog) {
        AlertDialog(
            onDismissRequest = { showFormatActionDialog = false },
            containerColor = DarkSurface,
            title = {
                Text("تصدير [${exportTargetFormat.displayName}]", color = NeonCyan, fontWeight = FontWeight.Bold)
            },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    // Option 1: Direct to Downloads
                    Card(
                        colors = CardDefaults.cardColors(containerColor = DarkCard),
                        shape = RoundedCornerShape(10.dp),
                        border = BorderStroke(1.dp, DarkBorder),
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                showFormatActionDialog = false
                                viewModel.saveSubtitleToDownloads(context, exportTargetFormat)
                            }
                    ) {
                        Row(
                            modifier = Modifier.padding(14.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.Download, contentDescription = null, tint = NeonGreen)
                            Spacer(modifier = Modifier.width(10.dp))
                            Column {
                                Text("حفظ في مجلد التنزيلات (Downloads)", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                                Text("حفظ مباشر وسريع في الذاكرة العامة للهاتف", color = TextSecondary, fontSize = 11.sp)
                            }
                        }
                    }

                    // Option 2: Custom Directory via SAF
                    Card(
                        colors = CardDefaults.cardColors(containerColor = DarkCard),
                        shape = RoundedCornerShape(10.dp),
                        border = BorderStroke(1.dp, DarkBorder),
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                showFormatActionDialog = false
                                val base = doc?.fileName?.substringBeforeLast('.') ?: "translated_subtitles"
                                safCreateDocLauncher.launch("${base}.ara${exportTargetFormat.extension}")
                            }
                    ) {
                        Row(
                            modifier = Modifier.padding(14.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.Description, contentDescription = null, tint = NeonCyan)
                            Spacer(modifier = Modifier.width(10.dp))
                            Column {
                                Text("حفظ في مجلد مخصص (بجانب الفيديو)", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                                Text("اختر أي مجلد على جهازك عبر متصفح الملفات", color = TextSecondary, fontSize = 11.sp)
                            }
                        }
                    }

                    // Option 3: Share sheet
                    Card(
                        colors = CardDefaults.cardColors(containerColor = DarkCard),
                        shape = RoundedCornerShape(10.dp),
                        border = BorderStroke(1.dp, DarkBorder),
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                showFormatActionDialog = false
                                val uri = viewModel.exportSubtitleFile(context, exportTargetFormat)
                                if (uri != null) {
                                    val shareIntent = Intent(Intent.ACTION_SEND).apply {
                                        type = "application/x-subrip"
                                        putExtra(Intent.EXTRA_STREAM, uri)
                                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                    }
                                    context.startActivity(Intent.createChooser(shareIntent, "مشاركة ملف الترجمة"))
                                }
                            }
                    ) {
                        Row(
                            modifier = Modifier.padding(14.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.Share, contentDescription = null, tint = AmberAccent)
                            Spacer(modifier = Modifier.width(10.dp))
                            Column {
                                Text("مشاركة الملف مع التطبيقات", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                                Text("إرسال عبر واتساب، تيليجرام، أو التخزين السحابي", color = TextSecondary, fontSize = 11.sp)
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showFormatActionDialog = false }) {
                    Text("إغلاق", color = TextSecondary)
                }
            }
        )
    }

    // Modal Loading Progress Dialog (Prevents UI freezing and shows real-time progress)
    if (isLoading) {
        Dialog(
            onDismissRequest = { /* Don't dismiss during background task */ },
            properties = DialogProperties(dismissOnBackPress = false, dismissOnClickOutside = false)
        ) {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(20.dp),
                border = BorderStroke(1.dp, NeonCyan.copy(alpha = 0.6f)),
                modifier = Modifier.fillMaxWidth(0.92f)
            ) {
                Column(
                    modifier = Modifier.padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    CircularProgressIndicator(
                        color = NeonCyan,
                        strokeWidth = 3.dp,
                        modifier = Modifier.size(50.dp)
                    )
                    Spacer(modifier = Modifier.height(18.dp))
                    Text(
                        text = loadingMessage.ifBlank { "جاري معالجة البيانات..." },
                        color = TextPrimary,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = "يُرجى الانتظار، جاري العمل في الخلفية دون تجميد التطبيق...",
                        color = TextSecondary,
                        fontSize = 11.sp,
                        textAlign = TextAlign.Center
                    )
                }
            }
        }
    }
}

private fun queryFileName(context: android.content.Context, uri: Uri): String? {
    var name: String? = null
    val cursor = context.contentResolver.query(uri, null, null, null, null)
    cursor?.use {
        if (it.moveToFirst()) {
            val nameIndex = it.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (nameIndex != -1) {
                name = it.getString(nameIndex)
            }
        }
    }
    return name
}
