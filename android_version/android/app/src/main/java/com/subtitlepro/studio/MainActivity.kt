package com.subtitlepro.studio

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection
import com.subtitlepro.studio.ui.components.AppBottomBar
import com.subtitlepro.studio.ui.components.AppTopBar
import com.subtitlepro.studio.ui.screens.CharactersGlossaryScreen
import com.subtitlepro.studio.ui.screens.LivePreviewScreen
import com.subtitlepro.studio.ui.screens.LogsScreen
import com.subtitlepro.studio.ui.screens.ProviderSettingsScreen
import com.subtitlepro.studio.ui.screens.StudioScreen
import com.subtitlepro.studio.ui.theme.DarkBackground
import com.subtitlepro.studio.ui.theme.SubtitleProTheme
import com.subtitlepro.studio.viewmodel.MainViewModel
import android.os.Build
import com.subtitlepro.studio.engine.service.TranslationForegroundService
import java.io.BufferedReader
import java.io.InputStreamReader

class MainActivity : ComponentActivity() {

    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Request notification permission on Android 13+ (API 33+) for foreground service
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 101)
            }
        }

        // Connect cancel action from foreground service notification
        TranslationForegroundService.onCancelCallback = {
            viewModel.cancelTranslation()
        }

        handleIncomingIntent(intent)

        setContent {
            SubtitleProTheme {
                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                    SubtitleProApp(viewModel)
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIncomingIntent(intent)
    }

    private fun handleIncomingIntent(intent: Intent?) {
        val uri: Uri? = intent?.data
        if (uri != null) {
            val fileName = queryFileName(uri) ?: "subtitles.ass"
            viewModel.loadSubtitleFromUri(this, uri, fileName)
        }
    }

    private fun queryFileName(uri: Uri): String? {
        var name: String? = null
        val cursor = contentResolver.query(uri, null, null, null, null)
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
}

@Composable
fun SubtitleProApp(viewModel: MainViewModel) {
    var selectedTab by remember { mutableStateOf(0) }
    val status by viewModel.status.collectAsState()

    Scaffold(
        containerColor = DarkBackground,
        topBar = { AppTopBar(status = status) },
        bottomBar = {
            AppBottomBar(
                selectedIndex = selectedTab,
                onSelectTab = { selectedTab = it }
            )
        }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            when (selectedTab) {
                0 -> StudioScreen(viewModel = viewModel)
                1 -> LivePreviewScreen(viewModel = viewModel)
                2 -> CharactersGlossaryScreen(viewModel = viewModel)
                3 -> ProviderSettingsScreen(viewModel = viewModel)
                4 -> LogsScreen(viewModel = viewModel)
            }
        }
    }
}
